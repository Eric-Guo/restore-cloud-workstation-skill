# Font recovery

Restore fonts only when requested or needed for the current rendering task. This public example includes no private font manifest, font archive, cache location, proprietary font, or automatic installer.

## Establish the required set

Inspect actual installed files and the document's effective fonts, including theme/master/layout inheritance, language, weight, and text runs. A declaration or successful fallback match is not proof that the original font exists. Do not download an entire multilingual font catalog because it appears in theme metadata. Keep document text and business details out of font manifests.

Use the user's current approved font set when one exists. Otherwise resolve exact families/styles and immutable versions from official projects, for example [Inter](https://github.com/rsms/inter), [Lato](https://www.latofonts.com/), [Montserrat](https://github.com/JulietaUla/Montserrat), or [Source Han Sans](https://github.com/adobe-fonts/source-han-sans). Record public source URL/revision, expected file and archive hashes/sizes, formats, licenses/notices, and family/style metadata in a new task-specific manifest. These are source examples, not an instruction to install every listed family or choose the latest version silently.

Read the applicable license and retain complete notices with a downloaded package. Do not treat embedding flags or a copied file as proof of redistribution rights. Preserve original family/style metadata; never rename font internals to impersonate a missing commercial font.

## Optional private cache

An owner-only cache can avoid repeat downloads but does not replace official provenance. Find the user-approved package through authorized storage metadata. Verify identity, owner, current permissions, size, independently recorded hash, and exact manifest before opening it. Keep its links/IDs and private records outside this public repository. Do not upload fonts or expand sharing without the applicable permission.

Inspect archives before extraction. Bound file count, total expanded size, and compression ratio. Reject absolute/traversing or colliding paths, duplicates, links, special entries, and encrypted members. Extract only validated regular files into fresh private staging. Hash-check every listed font and notice. Treat a bundled helper as untrusted code until its source and provenance are reviewed; a manifest cannot authorize its own execution.

A failed cache route does not require abandoning an authorized official-source restore. Do not download the same package twice merely to exercise both routes.

## Install and verify without overwriting

Install only in a dedicated user-level directory under the intended XDG/HOME configuration. Do not overwrite system fonts or unrelated user configuration. Preflight every target; skip identical content and stop on different hashes, symlinks, or unexpected files. Preserve sources, versions, licenses, and notices alongside the package.

Refresh the relevant user font cache. Use `fc-scan` on each actual file and `fc-match` to verify the selected family, style, and file. Compare that selected file's hash with the manifest. Inspect a non-sensitive Chinese/Latin sample for missing glyphs, clipping, and incorrect weight; separately re-render representative real pages when that task is authorized.

Same-font legacy-name normalization differs from font substitution. An optional exact-name Fontconfig rule must map to a genuinely matching family/weight and be reviewed like any other configuration. Substituting Noto or Source Han for a missing commercial family is a deliberate rendering choice, not restoration of the original or a promise of identical metrics. Do not silently alter the source document, install broad host aliases, or reuse an unlicensed machine font archive.

Report verified or installed families/styles, source versions, skips/conflicts, actual selection checks, sample-render results, and unresolved originals or explicit substitutes. Skill maintenance uses fixtures and verification only, never a live font installation.
