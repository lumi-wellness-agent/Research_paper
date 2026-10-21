# LUMI paper sync — 2026-10-22

## Actual import status

Four of the eight previously missing PDFs have been imported and validated. P31 now has a user-supplied manuscript (DOCX and a 22-page PDF conversion), but its referenced Tables 1–4 are absent. P12, P13 and P30 remain missing; P31 still needs a complete version. A bibliography entry is not a PDF upload.

| ID | Result | Title | Source / remaining blocker |
|---|---|---|---|
| P12 | Missing | Building mindfulness bottom-up: Meditation in natural settings supports open monitoring and attention restoration | https://doi.org/10.1016/j.concog.2018.01.008 — publisher subscription; author-hosted Academia download returned HTTP 403. |
| P13 | Missing | A natural meditation setting improves compliance with mindfulness training | https://doi.org/10.1016/j.jenvp.2019.05.008 — publisher subscription; DiVA has no full text; author-hosted Academia download returned HTTP 403. |
| P21 | Imported | Nature experience reduces rumination and subgenual prefrontal cortex activation | https://europepmc.org/articles/PMC4507237?pdf=render — 6 pages, 712,963 bytes. |
| P30 | Missing | Mechanisms of Anxiety Reduction During Adult Coloring: Mindfulness, Flow, Enjoyment, and Distraction | https://doi.org/10.1007/s12671-025-02586-9 — subscription article; CSUS record and ResearchGate preview do not provide the complete paper. |
| P31 | Supplied manuscript; tables missing | Cognitive and Affective Benefits of Coloring: Two Randomized Controlled Crossover Studies | User-supplied Cognitivebenefitsofcoloring.docx, preserved unchanged in color/ with a PDF conversion (22 pages). The running title and abstract identify P31; no title page or Tables 1–4 are included. DOI: https://doi.org/10.1080/07421656.2019.1645498. These files are labelled user-supplied manuscript and do not count as a verified complete import. |
| P32 | Imported | Colouring-in, a Distraction Technique? | https://api.figshare.com/v2/articles/29747162 — migrated Exeter repository; DrewN.pdf, 130 pages, 1,509,172 bytes (complete thesis containing the study). |
| P33 | Imported | An Experimental Exploration of the Effects of Exposure to Images of Nature on Rumination | https://mdpi-res.com/d_attachment/ijerph/ijerph-15-00300/article_deploy/ijerph-15-00300.pdf — 19 pages, 2,032,615 bytes. |
| P34 | Imported | Effect of the Art Coloring Online Coloring Game on Subjective Well-Being Increase and Anxiety Reduction During the COVID-19 Pandemic | https://games.jmir.org/2022/3/e37026/PDF — 13 pages, 1,829,029 bytes. Correct article PMCID: PMC9273045. |

The imported files retain the authors' original contents and copyright notices. Availability in this private research repository does not grant further redistribution rights.

### Attribution

- P21: Bratman, G. N., Hamilton, J. P., Hahn, K. S., Daily, G. C., & Gross, J. J. (2015). PNAS, 112(28), 8567–8572. https://doi.org/10.1073/pnas.1510459112
- P32: Drew, Neil (2018). Doctor of Clinical Psychology thesis, University of Exeter. https://hdl.handle.net/10871/34176
- P33: Golding, S. E., Gatersleben, B., & Cropley, M. (2018). IJERPH, 15(2), 300. https://doi.org/10.3390/ijerph15020300 — CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- P34: Xi, J., et al. (2022). JMIR Serious Games, 10(3), e37026. https://doi.org/10.2196/37026 — CC BY 4.0: https://creativecommons.org/licenses/by/4.0/

## What was fixed

The old workflow listed only two papers, used an incorrect PMC fallback for P34, and swallowed every download failure. Consequently, the original runs reported success with zero added PDFs.

The replacement checks all eight targets, rejects HTML and PDFs with a mismatched DOI/title, preserves successful partial imports, and fails the final check until all eight PDFs exist. Each run provides a per-paper summary and a JSON artifact. The workflow also runs when a PDF is added to the relevant folders, allowing manually supplied originals to be verified.

Some public download servers reject GitHub-hosted runner requests. P21 and P34 were therefore downloaded and validated separately, then committed directly. Retrying the same blocked URL is not a guarantee of completion.

## Completing the outstanding imports

Obtain the complete PDFs for P12, P13, P30 and P31 through an available publisher, institutional or author-provided route, and place them at the exact target paths listed in `.github/scripts/import_lumi_papers.py`. The workflow will validate them on the next run.

## Pending identity check from the original comparison

Existing `ART/Attention Restoration Theory.pdf` and `ART/Journal of Environmental Psychology.pdf` have generic filenames. Their correspondence to P04/P06 was not audited as part of this workflow repair.
