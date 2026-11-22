# Design

JobFinder's look is **Card Catalogue**: a library card file. Every job is a card you file, pull out and annotate. Warm card-stock neutrals, near-black ink, and one green tab that marks what matters. Why this direction won, and the two alternatives, are in [DECISIONS.md](DECISIONS.md) (#195–#201). The option sheets are in [docs/design-options/](docs/design-options/).

## Principles

1. **Restraint over decoration.** Personality comes from a few small, consistent details, not from effects.
2. **One accent, two meanings.** Green means "do this next" (the primary button) or "good fit" (a score of 70+ and met requirements). Nothing else is green.
3. **Typography does the work.** Clear size steps, generous line height, plain words.
4. **Fewer things per screen.** If it isn't needed to decide or act, it sits behind a tab, "More" or a disclosure.
5. **Resume documents are not branded.** The PDF and DOCX stay plain for ATS software.

## Tokens

All colours, the radius and the elevation live in `frontend/src/index.css` (`:root`). Components use the token classes (`bg-fog`, `text-muted-foreground`, `bg-selected`, `text-danger`, …), never raw Tailwind colours.

| Token | Value | Use |
|---|---|---|
| `--fog` | #F6F5F1 | Page background |
| `--background` / `--card` | #FFFFFF | Cards, sidebar, inputs, dialogs |
| `--foreground` | #1D2125 | Text (14.8:1 on the page) |
| `--muted-foreground` | #5C6166 | Secondary text (5.7:1) |
| `--border` | #E3E0D8 | Card and table borders |
| `--input` | #949087 | Form control edges (3.2:1) |
| `--primary` | #2E6B4F | **The accent**: primary button, good-score base line, met ticks |
| `--accent` / `--accent-foreground` | #E6F0EA / #245A41 | Good-score fill and text |
| `--selected` | #EBE8E0 | Current nav item, chosen chip or toggle (neutral) |
| `--attention*` | #8A5A00 on #FBF1DC | Partial score, warnings |
| `--danger*` | #A23B2E on #F9E6E2 | Failed hard requirement, possibly invented AI content, delete |
| `--score-weak` | #ECEBE6 | Weak score fill (weak is not an error) |
| `--ring` | #1D2125 | Focus outline (ink, so focus never looks like a primary action) |
| `--radius` | 6 px | Cards, controls, dialogs. Small chips use 3–4 px |
| `--shadow-pop` | soft, one level | Only for floating things: toast, menus, dialogs, a dragged card |

## Type

- **Public Sans** (variable, bundled): everything you read and use. Body 15 px / 1.55; captions 13 px minimum.
- **Schibsted Grotesk** (variable, bundled): page titles (28 px), section headings (18 px), the logo and the score numbers only.

## Signature details

- **Logo:** an index card with a green tab and two ruled lines, drawn on a 32-unit grid with 2.4-unit strokes, so it reads at 16 px. The same drawing is the favicon.
- **Score badge:** a file tab with a rounded top and a flat 2 px base line in the score's colour. Green is 70+, amber is 50–69, neutral is below 50 and red is only for a failed hard requirement. A rough estimate gets a dashed base line and a "~". It's the same shape in every list, card and header.
- **Flat surfaces:** cards are separated by 1 px borders, not shadows.
- **Toggles** (Kanban/Table, Accept/Reject) use the neutral `selected` button style with `aria-pressed`, not the accent.

## Voice

Plain, short and friendly, saying what it means for the user: "You're missing 2 skills", "Required skill, not in your bank yet", "You're all caught up." Empty states are one sentence plus one action, with no illustrations.

## Motion and accessibility

- The toast fades in over 160 ms. A global `prefers-reduced-motion` rule switches animations and transitions off.
- Every text pair meets WCAG AA. Focus is a 2 px ink outline, there's a skip link, and every control can be reached by keyboard.
- There are no emoji. Status icons are lucide drawings with accessible names.
