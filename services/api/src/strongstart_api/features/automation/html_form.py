"""Bounded, non-executing saved-HTML form parser (parser ``b2-html-form/1``).

Uses the standard-library tokenizer (``html.parser``) to build a small element tree.
It never executes scripts, evaluates styles, resolves URLs, follows links or loads
resources. Script/style text is kept out of extracted text and only counted.

Supported patterns (anything else is reported, not guessed):

- ``<label for=ID>`` and wrapping ``<label>`` for question wording; a leading
  ``"N."``/``"N)"`` in the label is recorded as the original number;
- ``<fieldset>``/``<legend>``: legend of a radio/checkbox group is its question text,
  otherwise the legend is the enclosing section; ``<h1>-<h4>`` inside a form set the
  section for following controls;
- ``aria-describedby`` element text as exact instructions;
- ``textarea``; ``input`` text/email/url/tel/search/number/radio/checkbox/file; ``select``
  with ``option`` values/labels;
- attributes ``required``/``aria-required``, ``maxlength``, ``min``/``max``/``step``,
  ``accept``, ``multiple``, ``hidden``;
- ``data-fixture-*`` attributes are *declared fixture metadata* (question IDs,
  conditions, attachment size/count, stream) and are labelled as such.

Unsupported: contenteditable/ARIA widgets, custom elements, other input types, JS
logic. Duplicate DOM IDs among controls are an error (never renumbered).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Literal

from strongstart_contracts.automation_intake import (
    AttachmentSpec,
    ChoiceOption,
    ConditionRecord,
    ExactText,
    Finding,
    SourceLocator,
)
from strongstart_contracts.common import SourceReference

from .intake_errors import duplicate_id
from .normalize import AnswerKind, LimitDraft, QuestionDraft, RequiredStatus, display, exact

PARSER_ID = "b2-html-form"
PARSER_VERSION = "1"
MAX_HTML_BYTES = 512 * 1024
MAX_ELEMENTS = 5000
MAX_CONTROLS = 300
EXCERPT_CHARS = 20_000

VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source",
    "track", "wbr", "param",
}  # fmt: skip
NON_TEXT = {"script", "style", "template", "noscript"}
RESOURCE_TAGS = {"img", "script", "link", "iframe", "source", "video", "audio", "object", "embed"}
TEXT_INPUTS = {"text", "email", "url", "tel", "search"}
SUPPORTED_INPUTS = TEXT_INPUTS | {"number", "radio", "checkbox", "file"}
IGNORED_INPUTS = {"hidden", "submit", "button", "reset", "image"}
_NUMBER_RE = re.compile(r"^\s*(\d{1,3}[A-Za-z]?)[.)]\s+")
_STABLE = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")

SourceRefFactory = Callable[[str], SourceReference]


@dataclass(eq=False)
class Node:
    tag: str
    attrs: dict[str, str]
    parent: Node | None
    line: int
    col: int
    index: int
    children: list[Node | str] = field(default_factory=list)

    def ancestors(self) -> list[Node]:
        out: list[Node] = []
        n = self.parent
        while n is not None:
            out.append(n)
            n = n.parent
        return out


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("#document", {}, None, 1, 0, -1)
        self.stack: list[Node] = [self.root]
        self.nodes: list[Node] = []
        self.limit_reached = False
        self.script_count = 0

    def _open(self, tag: str, attrs: list[tuple[str, str | None]], void: bool) -> None:
        if len(self.nodes) >= MAX_ELEMENTS:
            self.limit_reached = True
            return
        top = self.stack[-1]
        if tag == "option" and top.tag == "option":
            self.stack.pop()
        if tag in ("p", "li") and top.tag == tag:
            self.stack.pop()
        parent = self.stack[-1]
        amap: dict[str, str] = {}
        for k, v in attrs:
            amap.setdefault(k, v if v is not None else "")
        line, col = self.getpos()
        node = Node(tag, amap, parent, line, col, len(self.nodes))
        parent.children.append(node)
        self.nodes.append(node)
        if tag == "script":
            self.script_count += 1
        if not void and tag not in VOID:
            self.stack.append(node)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._open(tag, attrs, False)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._open(tag, attrs, True)

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data: str) -> None:
        if not self.limit_reached:
            self.stack[-1].children.append(data)


def text_content(node: Node, *, skip_controls: bool = False) -> str:
    parts: list[str] = []

    def walk(n: Node) -> None:
        for c in n.children:
            if isinstance(c, str):
                parts.append(c)
            elif c.tag in NON_TEXT or (skip_controls and c.tag in ("select", "textarea")):
                continue
            else:
                walk(c)

    walk(node)
    return "".join(parts)


def _path(node: Node) -> str:
    chain = [node, *node.ancestors()]
    out: list[str] = []
    for n in chain:
        if n.tag in ("#document", "html", "body"):
            break
        part = n.tag
        if n.attrs.get("id"):
            part += f"#{n.attrs['id']}"
        elif n.attrs.get("name"):
            part += f"[name={n.attrs['name']}]"
        out.append(part)
        if n.tag == "form":
            break
    return " > ".join(reversed(out))


def _loc(node: Node) -> SourceLocator:
    return SourceLocator(kind="html_element", value=_path(node), line=node.line, column=node.col)


def _is_hidden(node: Node) -> bool:
    for n in [node, *node.ancestors()]:
        if "hidden" in n.attrs:
            return True
        style = n.attrs.get("style", "").replace(" ", "").lower()
        if "display:none" in style or "visibility:hidden" in style:
            return True
    return False


def _slug(value: str) -> str:
    s = re.sub(r"[^a-z0-9._:-]+", "-", value.lower()).strip("-.:_")
    return s[:120]


@dataclass
class HtmlParse:
    drafts: list[QuestionDraft]
    findings: list[Finding]
    title: ExactText | None
    form_id: str | None
    controls_seen: int
    unsupported_elements: int
    limit_reached: bool
    excerpt: ExactText | None
    excerpt_truncated: bool


def parse_html(text: str, make_source_ref: SourceRefFactory) -> HtmlParse:
    builder = _TreeBuilder()
    builder.feed(text)
    builder.close()
    nodes = builder.nodes
    findings: list[Finding] = []

    if builder.script_count:
        findings.append(
            Finding(
                code="script_content_inert",
                severity="info",
                message=f"{builder.script_count} script element(s) retained as inert evidence; "
                "not executed or interpreted.",
            )
        )
    resources = [
        n for n in nodes if n.tag in RESOURCE_TAGS and ("src" in n.attrs or "href" in n.attrs)
    ]
    if resources:
        findings.append(
            Finding(
                code="external_reference_not_loaded",
                severity="info",
                message=f"{len(resources)} resource reference(s) were not loaded or followed.",
            )
        )

    by_id: dict[str, list[Node]] = {}
    for n in nodes:
        if "id" in n.attrs:
            by_id.setdefault(n.attrs["id"], []).append(n)
    labels_for: dict[str, Node] = {}
    wrap_label: dict[int, Node] = {}
    for n in nodes:
        if n.tag == "label":
            if n.attrs.get("for"):
                labels_for.setdefault(n.attrs["for"], n)
    for n in nodes:
        if n.tag in ("input", "textarea", "select"):
            for a in n.ancestors():
                if a.tag == "label":
                    wrap_label[n.index] = a
                    break

    def is_control(n: Node) -> bool:
        if n.tag in ("textarea", "select"):
            return True
        if n.tag == "input":
            return n.attrs.get("type", "text").lower() not in IGNORED_INPUTS
        return (
            "contenteditable" in n.attrs
            or n.attrs.get("role") in ("textbox", "combobox", "listbox", "slider", "spinbutton")
            or "-" in n.tag
        )

    controls = [n for n in nodes if is_control(n)]
    submit_controls = [
        n
        for n in nodes
        if (n.tag == "button" and n.attrs.get("type", "submit").lower() == "submit")
        or (n.tag == "input" and n.attrs.get("type", "").lower() in ("submit", "image"))
    ]
    if submit_controls:
        findings.append(
            Finding(
                code="submission_control_present",
                severity="info",
                message=f"{len(submit_controls)} submit control(s) present; this tool has no "
                "submit/sign capability.",
            )
        )
    dom_dupes = [i for i, ns in by_id.items() if len([x for x in ns if is_control(x)]) > 1]
    if dom_dupes:
        raise duplicate_id(
            "multiple form controls share a DOM id; nothing was renumbered", dom_dupes
        )

    truncated_controls = len(controls) > MAX_CONTROLS
    controls = controls[:MAX_CONTROLS]
    if builder.limit_reached or truncated_controls:
        findings.append(
            Finding(
                code="element_limit_reached",
                severity="warning",
                message=f"Element/control limits reached ({MAX_ELEMENTS}/{MAX_CONTROLS}); "
                "coverage is partial.",
            )
        )

    headings = [n for n in nodes if n.tag in ("h1", "h2", "h3", "h4")]
    form = next((n for n in nodes if n.tag == "form"), None)
    form_id = None
    if form is not None:
        declared = form.attrs.get("data-fixture-form-id", "")
        form_id = declared if _STABLE.match(declared) else None

    def label_of(n: Node) -> Node | None:
        if n.attrs.get("id") and n.attrs["id"] in labels_for:
            return labels_for[n.attrs["id"]]
        return wrap_label.get(n.index)

    def described(n: Node) -> list[ExactText]:
        out: list[ExactText] = []
        for ref in n.attrs.get("aria-describedby", "").split()[:10]:
            targets = by_id.get(ref)
            if targets:
                out.append(exact(text_content(targets[0]), _loc(targets[0])))
        return out

    def section_of(n: Node, group_fieldset: Node | None) -> ExactText | None:
        for a in n.ancestors():
            if a.tag == "fieldset" and a is not group_fieldset:
                legend = next(
                    (c for c in a.children if isinstance(c, Node) and c.tag == "legend"), None
                )
                if legend is not None:
                    return exact(text_content(legend), _loc(legend))
            if a.tag == "form":
                break
        owner_form = next((a for a in n.ancestors() if a.tag == "form"), None)
        prior = [
            h
            for h in headings
            if h.index < n.index and (owner_form is None or owner_form in h.ancestors())
        ]
        return exact(text_content(prior[-1]), _loc(prior[-1])) if prior else None

    def condition_of(n: Node) -> list[ConditionRecord]:
        for a in [n, *n.ancestors()]:
            if "data-fixture-condition" in a.attrs:
                dep = a.attrs.get("data-fixture-condition-question", "")
                return [
                    ConditionRecord(
                        predicate_text=a.attrs["data-fixture-condition"],
                        depends_on_question_id=dep if _STABLE.match(dep) else None,
                        expected_value=a.attrs.get("data-fixture-condition-value"),
                        basis="declared_fixture_metadata",
                        status="declared_unverified",
                        locator=_loc(a),
                    )
                ]
        return []

    drafts: list[QuestionDraft] = []
    unsupported = 0
    grouped: dict[tuple[int, str], list[Node]] = {}
    group_order: list[tuple[int, str]] = []
    items: list[tuple[str, Node | tuple[int, str]]] = []
    for n in controls:
        itype = n.attrs.get("type", "text").lower() if n.tag == "input" else ""
        if n.tag == "input" and itype in ("radio", "checkbox") and n.attrs.get("name"):
            owner = next((a for a in n.ancestors() if a.tag == "form"), None)
            key = (owner.index if owner else -1, n.attrs["name"])
            if key not in grouped:
                grouped[key] = []
                group_order.append(key)
                items.append(("group", key))
            grouped[key].append(n)
        else:
            items.append(("single", n))

    for order, (kind, item) in enumerate(items):
        if kind == "group":
            assert isinstance(item, tuple)
            members = grouped[item]
            drafts.append(
                _group_draft(order, item[1], members, make_source_ref, label_of, described,
                             section_of, condition_of)
            )  # fmt: skip
            continue
        assert isinstance(item, Node)
        draft, is_unsupported = _single_draft(
            order, item, make_source_ref, label_of, described, section_of, condition_of
        )
        unsupported += int(is_unsupported)
        drafts.append(draft)

    ids = [d.question_id for d in drafts]
    dup_q = {i for i in ids if ids.count(i) > 1}
    if dup_q:
        raise duplicate_id("derived question IDs collide; nothing was renumbered", list(dup_q))

    title_node = next((n for n in nodes if n.tag == "title"), None)
    title = exact(text_content(title_node), _loc(title_node)) if title_node else None
    excerpt = None
    excerpt_truncated = False
    if not drafts:
        body = next((n for n in nodes if n.tag == "body"), None)
        raw = text_content(body) if body is not None else text_content(builder.root)
        excerpt_truncated = len(raw) > EXCERPT_CHARS
        excerpt = exact(raw[:EXCERPT_CHARS], SourceLocator(kind="whole_input", value="body text"))
    return HtmlParse(
        drafts=drafts,
        findings=findings,
        title=title,
        form_id=form_id,
        controls_seen=len(controls),
        unsupported_elements=unsupported,
        limit_reached=builder.limit_reached or truncated_controls,
        excerpt=excerpt,
        excerpt_truncated=excerpt_truncated,
    )


def _question_id(n: Node, order: int, fallback: str | None) -> tuple[str, list[Finding]]:
    declared = n.attrs.get("data-fixture-question-id", "")
    if _STABLE.match(declared):
        return declared, []
    base = fallback or n.attrs.get("id") or n.attrs.get("name")
    if base and _slug(base):
        return f"html-{_slug(base)}", []
    qid = f"html-control-{order}"
    return qid, [
        Finding(
            code="missing_identifier",
            severity="warning",
            message="Control has no id/name; assigned a positional internal ID.",
            question_id=qid,
            locator=_loc(n),
        )
    ]


def _required(nodes: list[Node], texts: list[str], conditional: bool) -> RequiredStatus:
    if conditional:
        return "conditional"
    if any("required" in n.attrs or n.attrs.get("aria-required") == "true" for n in nodes):
        return "required"
    joined = " ".join(texts).lower()
    if "(optional)" in joined:
        return "optional"
    if "(required)" in joined:
        return "required"
    return "unknown"


def _split_number(text: str) -> str | None:
    m = _NUMBER_RE.match(text)
    return m.group(1) if m else None


def _hidden_finding(n: Node, qid: str) -> list[Finding]:
    if not _is_hidden(n):
        return []
    return [
        Finding(
            code="hidden_content",
            severity="info",
            message="Control is hidden in the saved markup (static state; dynamic logic unknown).",
            question_id=qid,
            locator=_loc(n),
        )
    ]


def _single_draft(
    order: int,
    n: Node,
    make_source_ref: SourceRefFactory,
    label_of: Callable[[Node], Node | None],
    described: Callable[[Node], list[ExactText]],
    section_of: Callable[[Node, Node | None], ExactText | None],
    condition_of: Callable[[Node], list[ConditionRecord]],
) -> tuple[QuestionDraft, bool]:
    qid, findings = _question_id(n, order, None)
    label = label_of(n)
    loc = _loc(n)
    if label is not None:
        text = exact(text_content(label, skip_controls=True), _loc(label))
    else:
        text = exact("", loc)
        findings.append(
            Finding(
                code="missing_label",
                severity="warning",
                message="Control has no associated label; question wording is unknown.",
                question_id=qid,
                locator=loc,
            )
        )
    itype = n.attrs.get("type", "text").lower() if n.tag == "input" else ""
    kind: AnswerKind
    unsupported = False
    if n.tag == "textarea" or (n.tag == "input" and itype in TEXT_INPUTS):
        kind = "text"
    elif n.tag == "input" and itype == "number":
        kind = "number"
    elif n.tag == "select":
        kind = "select"
    elif n.tag == "input" and itype == "file":
        kind = "file"
    elif n.tag == "input" and itype in ("radio", "checkbox"):
        kind = "choice"
    else:
        kind = "unsupported"
        unsupported = True
        findings.append(
            Finding(
                code="unsupported_widget",
                severity="blocker",
                message=f"Unsupported control <{n.tag}{' type=' + itype if itype else ''}"
                f"{' role=' + n.attrs['role'] if 'role' in n.attrs else ''}>; not normalized.",
                question_id=qid,
                locator=loc,
            )
        )
    instructions = described(n)
    conditions = condition_of(n)
    if conditions:
        findings.append(_declared_condition_finding(qid, conditions[0]))
    required = _required([n], [text.text], bool(conditions))
    stream = n.attrs.get("data-fixture-stream")
    stream = stream if stream and _STABLE.match(stream) else None
    limits: list[LimitDraft] = []
    if "maxlength" in n.attrs and n.attrs["maxlength"].strip().isdigit():
        limits.append(
            LimitDraft(
                kind="native_dom_maxlength",
                unit="utf16_code_units",
                evidence=exact(f'maxlength="{n.attrs["maxlength"]}"', loc),
                maximum=str(int(n.attrs["maxlength"].strip())),
            )
        )
    if kind == "number" and ("min" in n.attrs or "max" in n.attrs):
        mn, mx = n.attrs.get("min", "").strip(), n.attrs.get("max", "").strip()
        limits.append(
            LimitDraft(
                kind="native_dom_range",
                unit="amount",
                evidence=exact(f'min="{mn}" max="{mx}"', loc),
                minimum=mn if mn.isdigit() else None,
                maximum=mx if mx.isdigit() else None,
                stream=stream,
            )
        )
    choices: list[ChoiceOption] = []
    choice_mode: Literal["single", "multiple"] | None = None
    if kind == "select":
        choice_mode = "multiple" if "multiple" in n.attrs else "single"
        for opt in (c for c in _descendants(n) if c.tag == "option"):
            label_text = text_content(opt)
            choices.append(
                ChoiceOption(
                    value=opt.attrs.get("value", display(label_text)),
                    label=exact(label_text, _loc(opt)),
                )
            )
    attachment = _attachment(n, loc) if kind == "file" else None
    findings += _hidden_finding(n, qid)
    return (
        QuestionDraft(
            question_id=qid,
            order=order,
            text=text,
            answer_kind=kind,
            required_status=required,
            scope="unknown",
            source_ref=make_source_ref(f"L{n.line}:C{n.col} {loc.value}"),
            original_number=_split_number(text.text),
            section=section_of(n, None),
            instructions=instructions,
            conditions=conditions,
            limits=limits,
            choices=choices,
            choice_mode=choice_mode,
            attachment=attachment,
            findings=findings,
            primary_stream=stream,
        ),
        unsupported,
    )


def _descendants(n: Node) -> list[Node]:
    out: list[Node] = []
    for c in n.children:
        if isinstance(c, Node):
            out.append(c)
            out.extend(_descendants(c))
    return out


def _declared_condition_finding(qid: str, c: ConditionRecord) -> Finding:
    return Finding(
        code="condition_declared_fixture_metadata",
        severity="info",
        message=f'Condition "{c.predicate_text}" comes from declared fixture metadata, not '
        "from interpreting page logic.",
        question_id=qid,
        locator=c.locator,
    )


def _attachment(n: Node, loc: SourceLocator) -> AttachmentSpec:
    accept = n.attrs.get("accept")
    size = n.attrs.get("data-fixture-max-size-bytes", "")
    count = n.attrs.get("data-fixture-max-count", "")
    declared = size.isdigit() or count.isdigit()
    evidence = [exact(f'{k}="{n.attrs[k]}"', loc) for k in sorted(n.attrs) if k in (
        "accept", "multiple", "data-fixture-max-size-bytes", "data-fixture-max-count")]  # fmt: skip
    return AttachmentSpec(
        accepted_types=[t.strip() for t in accept.split(",") if t.strip()] if accept else None,
        max_size_bytes=int(size) if size.isdigit() else None,
        max_count=int(count) if count.isdigit() else (None if "multiple" in n.attrs else 1),
        multiple="multiple" in n.attrs,
        basis="declared_fixture_metadata" if declared else "native_dom_attribute",
        evidence=evidence,
    )


def _group_draft(
    order: int,
    name: str,
    members: list[Node],
    make_source_ref: SourceRefFactory,
    label_of: Callable[[Node], Node | None],
    described: Callable[[Node], list[ExactText]],
    section_of: Callable[[Node, Node | None], ExactText | None],
    condition_of: Callable[[Node], list[ConditionRecord]],
) -> QuestionDraft:
    first = members[0]
    fieldset = next((a for a in first.ancestors() if a.tag == "fieldset"), None)
    owner = (
        fieldset
        if fieldset is not None and all(fieldset in m.ancestors() for m in members)
        else None
    )
    qid_node = owner if owner is not None and "data-fixture-question-id" in owner.attrs else first
    qid, findings = _question_id(qid_node, order, name)
    legend = None
    if owner is not None:
        legend = next(
            (c for c in owner.children if isinstance(c, Node) and c.tag == "legend"), None
        )
    loc = _loc(owner or first)
    if legend is not None:
        text = exact(text_content(legend), _loc(legend))
    else:
        text = exact("", loc)
        findings.append(
            Finding(
                code="missing_label",
                severity="warning",
                message="Choice group has no legend; question wording is unknown.",
                question_id=qid,
                locator=loc,
            )
        )
    is_checkbox = first.attrs.get("type", "").lower() == "checkbox"
    choices: list[ChoiceOption] = []
    for m in members:
        lab = label_of(m)
        choices.append(
            ChoiceOption(
                value=m.attrs.get("value", "on"),
                label=exact(text_content(lab, skip_controls=True), _loc(lab)) if lab else None,
            )
        )
    instructions = described(owner) if owner is not None else []
    conditions = condition_of(first)
    if conditions:
        findings.append(_declared_condition_finding(qid, conditions[0]))
    findings += _hidden_finding(first, qid)
    return QuestionDraft(
        question_id=qid,
        order=order,
        text=text,
        answer_kind="choice",
        required_status=_required(members, [text.text], bool(conditions)),
        scope="unknown",
        source_ref=make_source_ref(f"L{loc.line}:C{loc.column} {loc.value}"),
        original_number=_split_number(text.text),
        section=section_of(first, owner),
        instructions=instructions,
        conditions=conditions,
        choices=choices,
        choice_mode="multiple" if is_checkbox and len(members) > 1 else "single",
        findings=findings,
    )
