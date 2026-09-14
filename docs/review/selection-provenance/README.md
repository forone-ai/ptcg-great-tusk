# Selection provenance

The preserved original manifest contains 1,241 positions from 690 games. Structural eligibility accepts 1,029 and rejects 212. The first 300 eligible confirmatory positions in each H band reconstruct the frozen 900-position manifest byte for byte, including its low-first execution order.

Previously inspected games are recorded as IDs and a checksum of the original source only; no outcome fields are included. The preparation code reads episode IDs from /private/tmp/trace2/results.json. In an isolated replication, construct its minimal results array (objects containing episode only) from previously-examined-game-ids.json, or change only that input path in a separately labelled replication copy. Do not replace the archived original source with this reduced file and claim an identical source checksum.

pilot-game-ids.json records both every reserved pilot game and selected IDs from each pilot run configuration. All are disjoint from the final 498 games. Metadata filenames are not evidence that a pilot completed or produced valid results.

The adjacent replay archive preserves only the selected 498 replay inputs. **Re-extracting the sample requires all 1,999 population replay inputs**, which are not bundled. population-replay-paths.json is a current pathname inventory, not a pre-freeze checksum record. Sampled-position reruns may use the preserved 498 inputs and a separate manifest with remapped paths.

Original and eligibility metadata retain their original bytes. Helper scripts were copied at packaging time; consult provenance-summary.json for which historical code hash can actually be verified. No confirmatory result or frozen runtime was modified.
