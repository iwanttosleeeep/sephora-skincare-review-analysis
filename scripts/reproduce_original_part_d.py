"""Reproduce the archived D submission with path-only substitutions into a new directory."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from project_paths import PART_E, require_analysis


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True,help='Must be a new directory')
    args=parser.parse_args()
    output=args.output_dir.resolve()
    if output.exists():
        parser.error('Output directory exists; choose a new location to preserve existing files.')
    output.mkdir(parents=True)
    with zipfile.ZipFile(ROOT/'preservation/part_d_original_submission.zip') as archive:
        name=next(x for x in archive.namelist() if x.endswith('.ipynb'))
        book=json.loads(archive.read(name))
    source=lambda i:''.join(book['cells'][i]['source'])
    text=source(1).replace('OUT = "outputs"','OUT = '+repr(str(output/'part_d')))
    book['cells'][1]['source']=text.splitlines(keepends=True)
    text=source(3)
    text='DATA_PATH = '+repr(str(require_analysis()))+'\n\n'+text[text.index('df = pd.read_parquet'):]
    book['cells'][3]['source']=text.splitlines(keepends=True)
    text=source(26)
    text='MODEL_PATH = '+repr(str(PART_E/'outputs/predicted_probabilities_skin_x_price.csv'))+'\n\n'+text[text.index('if MODEL_PATH is None:'):]
    book['cells'][26]['source']=text.splitlines(keepends=True)
    for cell in book['cells']:
        if cell['cell_type']=='code':
            cell['outputs']=[]
            cell['execution_count']=None
    env=os.environ.copy()
    env.update({'SEPHORA_RESULTS_DIR':str(output),'MPLBACKEND':'Agg','MPLCONFIGDIR':str(ROOT/'.cache/matplotlib'),
                'IPYTHONDIR':str(ROOT/'.cache/ipython'),'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','VECLIB_MAXIMUM_THREADS':'1'})
    (output/'logs').mkdir()
    with tempfile.TemporaryDirectory(prefix='part_d_original_') as work:
        notebook=Path(work)/'04_uncertainty_D_original_rerun.ipynb'
        notebook.write_text(json.dumps(book,ensure_ascii=False,indent=1)+'\n')
        with (output/'logs/original_rerun.log').open('w') as log:
            result=subprocess.run([sys.executable,str(ROOT/'scripts/run_analysis.py'),'--worker',str(notebook)],
                                  cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
    raise SystemExit(result.returncode)


if __name__=='__main__':
    main()
