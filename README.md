# What AI "thinking" looks like

Live page: https://aarushkandukoori.github.io/cot-traces/

Many chatbots now write out scratch work before they answer. People call it chain of thought. The big chatbot companies hide the raw scratch work or show a summary, but free open models show all of it.

This repo has real, unedited scratch work from two small open models on ten school-style questions, plus a simple web page for reading it:

- DeepSeek-R1-Distill-Qwen-1.5B
- Qwen3-1.7B (with thinking on, and again with thinking off)

Each model answered each question three times. The page highlights the moments where a model says "Wait" or "Hmm" and changes its mind, and the moments where it checks itself. It also flags runs where the final answer does not match where the thinking ended.

## What is in here

- `index.html`, `style.css`, `app.js` - the page. Plain HTML, CSS and JavaScript, no build step and no libraries, so it opens on any laptop or Chromebook.
- `data/traces.js` - every run, used by the page.
- `runs/` - the raw outputs, one JSON line per run, with the exact prompt, settings and seed, plus `stats.csv` with token counts and grades.
- `scripts/` - the code that made the runs (`gen.py`), the questions (`questions.json`), the hand grades (`grades_*.json`) and the script that counts, plots and builds the page data (`analyze.py`).

## How the runs were made

- 4-bit MLX versions of both models (`mlx-community/DeepSeek-R1-Distill-Qwen-1.5B-4bit`, `mlx-community/Qwen3-1.7B-4bit`), run with mlx_lm 0.32.0 on a MacBook Pro with an Apple M4, November 15, 2026.
- The question was the only input. No system prompt, no examples.
- Temperature 0.6 and top-p 0.95 for both models (each model card's recommended thinking settings), top-k 20 for Qwen3, at most 8,192 new tokens, seeds 0, 1 and 2.
- For "thinking off", Qwen3's chat template switch (`enable_thinking=False`) with the same settings.
- Right and wrong were graded by hand by reading every answer. The highlights are a plain word search.
- Each run sets its own random seed, so any single run can be redone on its own. The Qwen3 job was paused once to free memory on the laptop, so the timing fields of its first run include that pause, and its last two thinking runs and all thinking-off runs were finished in a second process with the same settings.

To redo a run on a Mac with Apple silicon (here, Qwen3 on the sheep riddle with seed 0):

```
pip install mlx-lm
python3 scripts/gen.py --model mlx-community/Qwen3-1.7B-4bit --mode think --seeds 0 --only sheep --top_k 20 --out redo/qwen3_sheep.jsonl
```

`gen.py` adds lines to the end of its `--out` file, so give it a new file name. `scripts/run_all.sh` redoes every run (it first moves the saved runs into `runs/old/`) and rebuilds the page data.

## Try the models yourself

With [Ollama](https://ollama.com) (Mac, Windows or Linux):

```
ollama run qwen3:1.7b
ollama run deepseek-r1:1.5b
```

Type any question and the thinking prints before the answer. Inside Ollama, `/set nothink` turns thinking off and `/set think` turns it back on.

## Licenses

Code: MIT. The model outputs come from DeepSeek-R1-Distill-Qwen-1.5B (MIT license) and Qwen3-1.7B (Apache 2.0).

Made by Aarush Kandukoori
