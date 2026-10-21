"""Import the eight missing LUMI papers; never report missing PDFs as success."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pypdf import PdfReader

MAX_BYTES = 30_000_000
PAPERS = [
    dict(id='P12', folder='ReST', title='Building mindfulness bottom-up: Meditation in natural settings supports open monitoring and attention restoration', doi='10.1016/j.concog.2018.01.008', urls=[], note='Publisher subscription; no public full-text copy verified.'),
    dict(id='P13', folder='ReST', title='A natural meditation setting improves compliance with mindfulness training', doi='10.1016/j.jenvp.2019.05.008', urls=[], note='Publisher subscription; no public full-text copy verified.'),
    dict(id='P21', folder='Mindfulness', title='Nature experience reduces rumination and subgenual prefrontal cortex activation', doi='10.1073/pnas.1510459112', urls=[
        'https://europepmc.org/articles/PMC4507237?pdf=render',
        'https://www.pnas.org/doi/pdf/10.1073/pnas.1510459112',
        'https://pmc.ncbi.nlm.nih.gov/articles/PMC4507237/pdf/pnas.201510459.pdf']),
    dict(id='P30', folder='color', title='Mechanisms of Anxiety Reduction During Adult Coloring: Mindfulness, Flow, Enjoyment, and Distraction', doi='10.1007/s12671-025-02586-9', urls=[], note='Subscription article; university record contains metadata only. Supply an authorized PDF.'),
    dict(id='P31', folder='color', title='Cognitive and Affective Benefits of Coloring: Two Randomized Controlled Crossover Studies', doi='10.1080/07421656.2019.1645498', urls=['https://uwe-repository.worktribe.com/OutputFile/848030'], note='Accepted manuscript listed at https://uwe-repository.worktribe.com/output/848019 ; automated retrieval returned HTTP 403.'),
    dict(id='P32', folder='color', title='Colouring-in, a Distraction Technique', doi=None, match='Colouring-in, a Distraction Technique', urls=['https://ndownloader.figshare.com/files/56769881', 'https://ore.exeter.ac.uk/repository/bitstream/handle/10871/34176/DrewN.pdf?sequence=1']),
    dict(id='P33', folder='color', title='An Experimental Exploration of the Effects of Exposure to Images of Nature on Rumination', doi='10.3390/ijerph15020300', urls=[
        'https://mdpi-res.com/d_attachment/ijerph/ijerph-15-00300/article_deploy/ijerph-15-00300.pdf',
        'https://www.mdpi.com/1660-4601/15/2/300/pdf']),
    dict(id='P34', folder='color', title='Effect of the Art Coloring Online Coloring Game on Subjective Well-Being Increase and Anxiety Reduction During the COVID-19 Pandemic', doi='10.2196/37026', urls=[
        'https://games.jmir.org/2022/3/e37026/PDF',
        'https://europepmc.org/articles/PMC9273045?pdf=render',
        'https://pmc.ncbi.nlm.nih.gov/articles/PMC9273045/pdf/games_v10i3e37026.pdf']),
]

def target_path(p):
    return Path(p['folder']) / (p['title'].replace(':', ' -') + '.pdf')

def normalize(text):
    return re.sub(r'[^a-z0-9]', '', text.lower())

def verify(data, paper):
    if len(data) > MAX_BYTES or not data.startswith(b'%PDF-'):
        raise ValueError('Response is not a PDF or exceeds size limit (possibly HTML/challenge page)')
    reader = PdfReader(io.BytesIO(data))
    if not reader.pages:
        raise ValueError('PDF has no pages')
    text = ''.join(page.extract_text() or '' for page in reader.pages[:3])
    normalized = normalize(text)
    identifiers = [paper.get('doi'), paper.get('match', paper['title'])]
    if not any(normalize(i) in normalized for i in identifiers if i):
        raise ValueError('PDF identity mismatch: expected DOI/title absent from first three pages')
    return dict(bytes=len(data), pages=len(reader.pages), sha256=hashlib.sha256(data).hexdigest())

def import_one(paper, verify_only=False):
    target = target_path(paper)
    errors = []
    if target.exists():
        try:
            return dict(id=paper['id'], path=str(target), status='verified', **verify(target.read_bytes(), paper))
        except Exception as error:
            # Do not overwrite a pre-existing file with unverified content.
            return dict(id=paper['id'], path=str(target), status='missing', errors=[str(error)])
    if not verify_only:
        for url in paper['urls']:
            try:
                request = urllib.request.Request(url, headers={'User-Agent': 'LUMI-PaperSync/2.0', 'Accept': 'application/pdf'})
                with urllib.request.urlopen(request, timeout=35) as response:
                    data = response.read(MAX_BYTES + 1)
                metadata = verify(data, paper)
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_suffix('.pdf.part')
                temporary.write_bytes(data)
                temporary.replace(target)
                print(f"DOWNLOADED {paper['id']} {target}", flush=True)
                return dict(id=paper['id'], path=str(target), status='downloaded', source=url, **metadata)
            except Exception as error:
                errors.append(f'{url}: {type(error).__name__}: {error}')
    return dict(id=paper['id'], path=str(target), status='missing', errors=errors or [paper.get('note', 'PDF not present')])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(lambda p: import_one(p, args.verify_only), PAPERS))
    Path('paper-import-results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
    complete = sum(r['status'] != 'missing' for r in results)
    lines = [f'## LUMI PDF import: {complete}/8 verified', '', '| ID | Result | File / reason |', '|---|---|---|']
    for result in results:
        detail = result['path'] if result['status'] != 'missing' else '; '.join(result['errors'])
        lines.append(f"| {result['id']} | {result['status']} | {detail.replace('|', '/').replace(chr(10), ' ')} |")
    summary = '\n'.join(lines) + '\n'
    print(summary)
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as stream:
            stream.write(summary)
    if complete != len(PAPERS):
        print(f'::error::{len(PAPERS)-complete} of 8 required papers are missing. See job summary / artifact.')
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
