# Pitfalls Research — AeroCloud Engine Risk Register

**Researched by:** Gemini CLI (April 2026)
**Stack:** Python 3.11 + PyTorch 2.7 CUDA + nvdiffrast + sentence-transformers + POT + pyribs + spaCy + scipy + svgwrite + FastAPI + Celery + Redis + PostgreSQL + pgvector + Rust/WASM + NVIDIA-Docker + Hostinger Cloud

## 1. Differentiable Rendering Instability

- **Warning sign:** NaN-Loss during optimization, "spaghetti gradients" (frayed geometry)
- **Prevention:** nvdiffrast antialiasing, gradient clipping, initialization with solid heuristics not pure noise
- **Phase:** 5 (Renderer-v1) / 6 (Inner Loop-v1)

## 2. PyTorch + CUDA Memory Management

- **Warning sign:** `RuntimeError: CUDA out of memory` despite free RAM, leaks via dangling autograd graphs
- **Prevention:** Explicit `.detach()` for metrics, `torch.cuda.empty_cache()` in loops, gradient checkpointing for large batches
- **Phase:** 5 (Renderer-v1) / 6 (Inner Loop-v1)

## 3. BERT in Production (Inference Drift)

- **Warning sign:** Tokenization errors on special characters, high cold-start latency
- **Prevention:** Pin sentence-transformers version, model warmup at container start, ONNX Runtime export for inference
- **Phase:** 8 (Semantic Vector Space)

## 4. Sinkhorn-Knopp Numerical Instability

- **Warning sign:** Numerical underflow in matrix scaling, fails to converge on sparse word distributions
- **Prevention:** Compute in log-space (log-sum-exp trick), adaptive ε regularization, POT library fallbacks
- **Phase:** 8 (Semantic Vector Space)

## 5. MAP-Elites Archive Saturation

- **Warning sign:** Archive only fills one corner (premature convergence), elites replaced by marginally-better but less-robust individuals
- **Prevention:** Well-chosen behavioral descriptors, novelty search components, periodic re-evaluation of elites
- **Phase:** 9 (Outer Loop-v1)

## 6. CQD Metric Implementation

- **Warning sign:** Incorrect normalization → scores >1.0, Monte-Carlo variance makes results incomparable
- **Prevention:** Fixed seeds for sampling, normalize against ideal-cloud lower bound, theta-sweep smoothing
- **Phase:** 11 (Outer Loop-v2)

## 7. Celery + GPU Task Zombies

- **Warning sign:** GPU memory stays allocated even though Celery task reports "finished", parallel access deadlocks
- **Prevention:** Limit `worker_max_tasks_per_child`, dedicated GPU pools, `atexit` handlers for CUDA context cleanup
- **Phase:** 12 (Production v1)

## 8. Async / Sync Mixing

- **Warning sign:** FastAPI event loop blocks during heavy compute, asyncpg errors in sync Celery context
- **Prevention:** Separate I/O-bound (async) from CPU-bound (sync/multiprocessing), use `run_in_executor`
- **Phase:** 12 (Production v1)

## 9. PostgreSQL pgvector Performance

- **Warning sign:** Linear scan despite index, high latency >100k vectors
- **Prevention:** Tune HNSW (`m`, `ef_construction`), PCA dimension reduction before storage if dim >1536
- **Phase:** 9 (Outer Loop-v1) — archive persistence / 12 (Production v1)

## 10. Hostinger VPS + NVIDIA-Docker

- **Warning sign:** Kernel header mismatch prevents driver loading, vGPU sharing causes unpredictable performance drops
- **Prevention:** Pinned base images (NVIDIA PyTorch), nvidia-smi monitoring, Docker Compose resource limits
- **Phase:** 1 (Foundation)

## 11. Determinism Loss

- **Warning sign:** Same input produces different word clouds across runs
- **Prevention:** Global seed for torch/numpy/random, `CUBLAS_WORKSPACE_CONFIG=:4096:8`, dataloader worker seeding
- **Phase:** 1 (Foundation) — central `set_seed()` function

## 12. Self-Play Feedback Loops

- **Warning sign:** AI learns "reward hacking" (maximizes metric via aesthetic exploits), diversity collapse
- **Prevention:** Adversarial reviewer model, penalty for out-of-bounds geometry, mix in real user data
- **Phase:** 10 (Self-Play)

## 13. Pareto-Front Scaling

- **Warning sign:** Pareto-dominance computation O(n²) bottleneck on large archives
- **Prevention:** Grid-based archive (pyribs), hypervolume approximation, periodic pruning
- **Phase:** 11 (Outer Loop-v2)

## 14. Seam Carving Artifacts

- **Warning sign:** Staircase patterns on diagonals, information loss in dense text clusters
- **Prevention:** Use Medial Axis Transform as guide, energy function weighting via saliency maps
- **Phase:** 12 (Production v1) — Export

## 15. Bezier Export Precision

- **Warning sign:** SVG renders differently in browser vs Adobe Illustrator (subpixel rounding)
- **Prevention:** High decimal precision, absolute (not relative) paths, embedded font hinting metadata
- **Phase:** 12 (Production v1) — Export

## 16. Security & Injection

- **Warning sign:** XSS via SVG color codes, path traversal in mask uploads, pickle deserialization of model checkpoints
- **Prevention:** Strict Pydantic schema validation, `safetensors` instead of `pickle`, SVG sanitizing
- **Phase:** 12 (Production v1)

## 17. Cost Runaway (GPU Billing)

- **Warning sign:** Celery retry loops keep expensive instances active unnecessarily
- **Prevention:** Hard timeouts on tasks, monitoring alerts on unusual traffic, auto-scaling policies
- **Phase:** 12 (Production v1)

## 18. Reproducibility (Environment Drift)

- **Warning sign:** "Works on my machine" effect, `:latest` container tags cause errors
- **Prevention:** `uv.lock` + SHA-pinned Docker images, document host kernel version
- **Phase:** 1 (Foundation) / 12 (Production v1)

## Risk Concentration

The two biggest technical hurdles per Gemini analysis:

1. **Phase 5 + 6:** Stable coupling of Differentiable Rendering with Loss + Adam under tight VRAM constraints
2. **Phase 12:** Async Celery stack under restrictive VPS conditions (cold-start, vGPU sharing)

**Critical foundation:** Pinning seeds and model versions in Phase 1 + Phase 8 is essential for QD archive validity in Phase 9 and beyond.

---
*Researched by Gemini CLI on 2026-04-07*
