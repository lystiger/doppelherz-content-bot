# Demo page design

Source: ui-ux-pro-max `search.py "health supplement brand content approval dashboard editorial" --design-system`
returned a near-black + gold editorial palette (kept) and a "Liquid Glass" style (rejected: Apple app chrome).
Retry `"editorial review dashboard light" --domain style` returned Editorial Grid and Data-Dense Dashboard.
Chosen: KOC Discovery B12 editorial layout (ranked rows, hairlines, serif headings) with Doppelherz logo colors.

| Token | Value | Use |
|---|---|---|
| Ground | `#F7F2EA` | Page background (logo cream, lightened) |
| Paper | `#FFFDF9` | Surfaces |
| Ink | `#16130F` | Text (logo black, warmed) |
| Ink 2 | `#5C554C` | Secondary text |
| Line | `#E7DCC9` | Hairlines |
| Gold | `#C3A063` | Logo frame, rules (decorative only) |
| Gold text | `#7D5F24` | Gold-toned text, 4.5:1+ on ground |
| Heart red | `#EC1C2D` | Logo heart mark only (white on it is 4.4:1, fails) |
| Red | `#C8102E` | Primary buttons, blocked state (white on it 5.9:1) |
| Green | `#2F5D50` / `#DCE8E2` | Scheduled |
| Amber | `#8A5A00` / `#FBEFD6` | Needs review |

Logo colors measured from `LOGO-DOPPELHERZ.png`: `#EC1C2D`, `#000002`, `#C3A063`, `#F0E7D8`.
Fonts: Newsreader (headings), Be Vietnam Pro (body), tabular numbers.
Always light, like KOC Discovery. Status never relies on color alone: every badge has a word.
