// Builds the summary table and the run list from data/traces.js.
// Plain JavaScript, no libraries, so it works on any school laptop or Chromebook.
(function () {
  "use strict";
  var META = window.COT_META;
  var RUNS = window.COT_RUNS;
  var NAMES = { r1: "DeepSeek-R1-Distill-Qwen-1.5B", q3: "Qwen3-1.7B", q3off: "Qwen3-1.7B, thinking off" };
  var ORDER = ["r1", "q3", "q3off"];

  // Wait / Hmm / Actually ... get a yellow highlight; double-check / verify ... get a green underline.
  var MARK_RE = /\b(wait|hmm+|hold on|actually|alternatively)\b|\b(double[- ]check\w*|let me check|let me verify|verify|make sure|let me confirm)\b/gi;

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function fmt(n) { return Number(n).toLocaleString("en-US"); }

  function highlight(text) {
    var frag = document.createDocumentFragment();
    var last = 0, m;
    MARK_RE.lastIndex = 0;
    while ((m = MARK_RE.exec(text)) !== null) {
      if (m.index > last) frag.appendChild(document.createTextNode(text.slice(last, m.index)));
      frag.appendChild(el("mark", m[1] ? "turn" : "check", m[0]));
      last = m.index + m[0].length;
    }
    if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
    return frag;
  }

  function buildSummary() {
    var tbody = document.querySelector("#summary tbody");
    var byQ = META.summary.by_question;
    META.questions.forEach(function (q) {
      var tr = el("tr");
      var th = el("th"); th.scope = "row"; th.textContent = q.short; th.title = q.text; tr.appendChild(th);
      tr.appendChild(el("td", "", q.gold));
      ["r1", "q3"].forEach(function (k) {
        var s = byQ[q.id] && byQ[q.id][k];
        tr.appendChild(el("td", "num", s ? s.correct + " of " + s.runs : "not run"));
        tr.appendChild(el("td", "num toks", s ? s.thinking.map(fmt).join(", ") : ""));
      });
      var off = byQ[q.id] && byQ[q.id].q3off;
      tr.appendChild(el("td", "num", off ? off.correct + " of " + off.runs : "not run"));
      tbody.appendChild(tr);
    });
  }

  function runCard(r) {
    var card = el("article", "run " + r.model);
    card.dataset.model = r.model;
    card.dataset.wrong = String(!r.correct);
    card.dataset.wait = String(r.waits > 0);
    card.dataset.mismatch = String(r.mismatch);

    var head = el("div", "head");
    head.appendChild(el("span", "who", NAMES[r.model]));
    head.appendChild(el("span", "small", "run " + (r.seed + 1)));
    var badge = el("span", "badge " + (r.correct ? "right" : "wrong"),
      r.correct ? "Right" : (r.finished ? "Wrong" : "No answer"));
    head.appendChild(badge);
    card.appendChild(head);

    var bits = [];
    if (r.mode === "think") {
      bits.push("thinking " + fmt(r.n_thinking) + " tokens" + (r.finished ? "" : " (hit the limit)"));
      if (r.waits) bits.push('"Wait" ' + r.waits + (r.waits === 1 ? " time" : " times"));
      if (r.checks) bits.push("checks " + r.checks);
    } else {
      bits.push("thinking turned off");
    }
    bits.push("answer " + fmt(r.n_answer) + " tokens");
    card.appendChild(el("div", "stats", bits.join(" | ")));

    var fin = el("p", "final");
    fin.appendChild(el("span", "k", "Final answer"));
    fin.appendChild(el("span", "v", r.final));
    card.appendChild(fin);
    if (r.mode === "think" && r.mismatch) {
      card.appendChild(el("p", "note", "The thinking ended at “" + r.think_end + "”, which does not match the final answer."));
    }
    if (r.note) card.appendChild(el("p", "note", r.note));

    if (r.mode === "think") {
      var d1 = el("details");
      d1.appendChild(el("summary", "", "Show the thinking (" + fmt(r.n_thinking) + " tokens)"));
      var t = el("div", "think");
      t.appendChild(highlight(r.thinking.trim()));
      d1.appendChild(t);
      card.appendChild(d1);
    }
    var d2 = el("details");
    d2.appendChild(el("summary", "", "Show the full answer, exactly as written"));
    d2.appendChild(el("div", "ans", r.answer || "(no answer: the model never stopped thinking)"));
    card.appendChild(d2);
    return card;
  }

  function buildList() {
    var list = document.getElementById("list");
    META.questions.forEach(function (q) {
      var group = el("section", "qgroup");
      group.dataset.qid = q.id;
      group.appendChild(el("h3", "", q.text));
      group.appendChild(el("p", "qmeta", q.kind + " | right answer " + q.gold));
      ORDER.forEach(function (k) {
        RUNS.filter(function (r) { return r.qid === q.id && r.model === k; })
          .sort(function (a, b) { return a.seed - b.seed; })
          .forEach(function (r) { group.appendChild(runCard(r)); });
      });
      list.appendChild(group);
    });
  }

  function applyFilters() {
    var form = document.getElementById("filters");
    var model = form.elements.model.value;
    var show = form.elements.show.value;
    var shown = 0;
    document.querySelectorAll(".qgroup").forEach(function (g) {
      var any = false;
      g.querySelectorAll(".run").forEach(function (c) {
        var ok = (model === "all" || c.dataset.model === model) &&
          (show === "all" || c.dataset[show === "wrong" ? "wrong" : show] === "true");
        c.hidden = !ok;
        if (ok) { any = true; shown++; }
      });
      g.hidden = !any;
    });
    document.getElementById("count").textContent = "Showing " + shown + " of " + RUNS.length + " runs.";
  }

  buildSummary();
  buildList();
  document.getElementById("filters").addEventListener("change", applyFilters);
  applyFilters();
})();
