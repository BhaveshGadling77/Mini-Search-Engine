#!/usr/bin/env bash
# WL2 NFR measurement harness.
# Run from the REPO ROOT (the folder that contains the Makefile):
#     bash wl2_measure.sh
# Optional env vars:  RUNS=5  Q_REPEAT=30  CORPUS=data/crawler.json  SCALE_BIG=1
# Everything is written to ./wl2_results/ ; paste wl2_results/summary.txt back to Claude.

set -u
OUT=wl2_results
CORPUS=${CORPUS:-data/crawler.json}
RUNS=${RUNS:-5}
Q_REPEAT=${Q_REPEAT:-30}
CLI=./build/search_cli
mkdir -p "$OUT"
: > "$OUT/summary.txt"
say() { echo "$*" | tee -a "$OUT/summary.txt"; }

stats() {  # stdin: one number per line -> "n mean min p95 max"
  sort -g | awk '{a[NR]=$1; s+=$1} END {
    if (NR==0) {print "n=0"; exit}
    i=int(0.95*NR+0.9999); if (i<1) i=1; if (i>NR) i=NR;
    printf "n=%d mean=%.3f min=%.3f p95=%.3f max=%.3f\n", NR, s/NR, a[1], a[i], a[NR]}'
}

# ---------------------------------------------------------------- 0. environment
say "##### 0. ENVIRONMENT"
{
  uname -srm
  g++ --version | head -1
  (command -v clang++ >/dev/null && clang++ --version | head -1) || echo "clang++: not installed"
  nproc 2>/dev/null
  grep -m1 "model name" /proc/cpuinfo 2>/dev/null
  free -m 2>/dev/null | sed -n 2p
} 2>&1 | tee "$OUT/env.txt" | tee -a "$OUT/summary.txt"

# ---------------------------------------------------------------- 1. build + warnings
say ""
say "##### 1. BUILD (make clean && make all) + compiler warnings"
make clean > /dev/null 2>&1
( time make all ) > "$OUT/build_cli.txt" 2>&1
say "cli build exit/real time:"
grep -E "^real" "$OUT/build_cli.txt" | tee -a "$OUT/summary.txt"
test -x "$CLI" && say "cli binary: OK" || say "cli binary: MISSING (build failed - see $OUT/build_cli.txt)"

# ---------------------------------------------------------------- 2. correctness tests
say ""
say "##### 2. CORRECTNESS TESTS"
make test-wl2 > "$OUT/tests_wl2.txt" 2>&1;      T1=$?
make test-boolean > "$OUT/tests_boolean.txt" 2>&1; T2=$?
say "make test-wl2      exit code: $T1   (0 = all passed)"
say "make test-boolean  exit code: $T2   (0 = all passed)"
say "--- tail of test-wl2:";     tail -n 12 "$OUT/tests_wl2.txt"     | tee -a "$OUT/summary.txt"
say "--- tail of test-boolean:"; tail -n 12 "$OUT/tests_boolean.txt" | tee -a "$OUT/summary.txt"
WARN=$(cat "$OUT/build_cli.txt" "$OUT/tests_wl2.txt" "$OUT/tests_boolean.txt" | grep -c "warning:")
say "total compiler warnings (-Wall -Wextra) across cli + tests: $WARN"

# ---------------------------------------------------------------- 3. boolean-op benchmarks
say ""
say "##### 3. BOOLEAN / SKIP-UNION BENCHMARKS ($RUNS repeated runs, each already a median of 7 samples)"
for i in $(seq 1 "$RUNS"); do
  make benchmark-union-big > "$OUT/union_big_run$i.txt" 2>&1
done
say "--- union_ vs union_with_skips, speedup per case, per run:"
for i in $(seq 1 "$RUNS"); do
  echo "run $i:" | tee -a "$OUT/summary.txt"
  grep -E "^Test:|Speedup|Correctness" "$OUT/union_big_run$i.txt" | tee -a "$OUT/summary.txt"
done
make benchmark-union-small > "$OUT/union_small.txt" 2>&1
make benchmark-skip-offsets > "$OUT/skip_offsets.txt" 2>&1
say "--- skip-offset comparison (plain vs sqrt vs fixed vs exponential), raw:"
cat "$OUT/skip_offsets.txt" | tee -a "$OUT/summary.txt"

# ---------------------------------------------------------------- 4. scalability + memory
say ""
say "##### 4. INDEX BUILD TIME + PEAK MEMORY vs CORPUS SIZE ($RUNS runs each)"
TIME=/usr/bin/time
if ! $TIME -f "%e %M" true > /dev/null 2>&1; then
  TIME=""
  say "NOTE: GNU /usr/bin/time not available -> peak memory will be skipped (Linux: sudo apt install time)"
fi
python3 - "$CORPUS" "$OUT" "${SCALE_BIG:-0}" <<'PY'
import json, sys
src, out, big = sys.argv[1], sys.argv[2], sys.argv[3]
docs = [json.loads(l) for l in open(src) if l.strip()]
def write(name, items):
    with open(f"{out}/corpus_{name}.jsonl", "w") as f:
        for d in items: f.write(json.dumps(d) + "\n")
for n in (100, 250, 500):
    write(str(n), docs[:n])
if big == "1":   # synthetic: repeat the corpus with fresh doc_ids (a heavier run; needs a few GB of RAM)
    items = []
    for k in range(2):
        for i, d in enumerate(docs):
            e = dict(d); e["doc_id"] = str(k * len(docs) + i + 1); items.append(e)
    write("1000", items)
PY
: > "$OUT/scale_raw.txt"
for f in "$OUT"/corpus_*.jsonl; do
  n=$(basename "$f" .jsonl | sed 's/corpus_//')
  for r in $(seq 1 "$RUNS"); do
    if [ -n "$TIME" ]; then
      $TIME -f "%e %M" -o "$OUT/_t.txt" "$CLI" "$f" <<< ":quit" > /dev/null 2>&1
      read -r secs kb < <(tail -n 1 "$OUT/_t.txt")
      echo "$n $secs $kb" >> "$OUT/scale_raw.txt"
    else
      s=$(date +%s.%N); "$CLI" "$f" <<< ":quit" > /dev/null 2>&1; e=$(date +%s.%N)
      echo "$n $(echo "$e - $s" | bc) NA" >> "$OUT/scale_raw.txt"
    fi
  done
done
say "docs | load+index time (s) [n mean min p95 max] | peak RSS (MB) [mean]"
for n in $(awk '{print $1}' "$OUT/scale_raw.txt" | sort -n | uniq); do
  T=$(awk -v n="$n" '$1==n {print $2}' "$OUT/scale_raw.txt" | stats)
  M=$(awk -v n="$n" '$1==n && $3!="NA" {s+=$3; c++} END {if (c) printf "%.0f", s/c/1024; else print "NA"}' "$OUT/scale_raw.txt")
  say "$n | $T | $M"
done
ls -l "$CORPUS" | awk '{printf "corpus file size: %.1f MB\n", $5/1048576}' | tee -a "$OUT/summary.txt"

# ---------------------------------------------------------------- 5. query latency (full CLI path, 500 docs)
say ""
say "##### 5. QUERY LATENCY via CLI ('Query time' ms, $Q_REPEAT repeats per query, warm index, $CORPUS)"
say "NOTE: CLI time includes resolve_query + fetching snippets for ALL hits + scoring/sorting."
run_q() {  # $1=label  $2=query
  for _ in $(seq 1 "$Q_REPEAT"); do echo "$2"; done > "$OUT/_q.txt"; echo ":quit" >> "$OUT/_q.txt"
  "$CLI" "$CORPUS" < "$OUT/_q.txt" 2>&1 | grep "^Query time:" | awk '{print $3}' > "$OUT/lat_$1.txt"
  hits=$(echo "$2" | "$CLI" "$CORPUS" 2>&1 | grep -cE '^[0-9]+\. \[')
  printf "%-10s %-22s hits=%-4s " "$1" "$2" "$hits" | tee -a "$OUT/summary.txt"
  stats < "$OUT/lat_$1.txt" | tee -a "$OUT/summary.txt"
}
run_q single   'search'
run_q and      'data AND search'
run_q or       'python OR linux'
run_q not      'NOT search'
run_q phrase   '"search engine"'
run_q prefix   'pyth*'
run_q suffix   '*tion'
run_q infix    'ser*er'
