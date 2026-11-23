# Development ownership and interview preparation

The initial project was generated with AI assistance in Codex. Automated checks and measurements do not establish that you personally understand the implementation. Review it, run the demo, and make your own meaningful extension before describing your contribution in an interview.

Be able to explain:
1. Why cosine similarity is a dot product after L2 normalization.
2. Why IDF reduces the weight of common tags.
3. Why C keeps the worst retained match at the heap root.
4. Why full ranking costs O(ND + N log k), and why native-buffer construction matters.
5. How likes persist, why liked items are excluded, and what happens with no history.
6. Why prepared-kernel speedup is different from API response time.
7. Why synthetic offline metrics do not establish real-user relevance.

## Record your own changes

Add date, problem, decision, code you reviewed or wrote, AI assistance, bug found and verification evidence here. No independent contribution is assumed yet.

## Resume wording to adapt after review

PinPoint — Personalized Recommendation Pipeline | Python, C, Java, SQLite

- Integrated a Java REST API with Python TF-IDF user profiles and a native C cosine-similarity/top-k library, supporting persistent likes, cold-start recommendations and shared-interest explanations.
- Validated C/Python ranking equivalence with randomized tests and HTTP integration tests; benchmarked native ranking with and without buffer-construction overhead.

If including a performance number, give its exact workload and scope from reports/BENCHMARK.md. Re-run the benchmark yourself. Do not claim Google/Pinterest affiliation, production scale, independent authorship, real-world accuracy or API-level speedups not measured here.
