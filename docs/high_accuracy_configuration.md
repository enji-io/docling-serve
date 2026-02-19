# High-accuracy model configuration

This document summarizes how to configure Docling Serve for heavier, higher-accuracy model variants at each processing stage. It is based on the options exposed by the API and server settings, and on the behavior of the upstream Docling and docling-jobkit libraries.

## Configuration matrix

| Stage | Option(s) for higher accuracy | Where to set | Prerequisites / notes |
|-------|-------------------------------|--------------|------------------------|
| **Table structure** | `table_mode`: use `"accurate"` (TableFormer accurate mode) | Request body or form (`table_mode`) | Default in API is `accurate`. Use `"fast"` only when speed is preferred. |
| **OCR** | `ocr_engine`: use `"auto"` (selects best available) or a specific engine (e.g. `"tesseract"`, `"easyocr"`) | Request body or form (`ocr_engine`) | Depends on installed engines and languages. See [Docling model catalog](https://docling-project.github.io/docling/usage/model_catalog/) for engine notes. |
| **PDF parsing** | `pdf_backend`: use `"dlparse_v4"` (default) for current backend | Request body or form (`pdf_backend`) | Other values: `pypdfium2`, `dlparse_v1`, `dlparse_v2`. |
| **Pipeline** | `pipeline`: use `"vlm"` for full-page vision-language conversion | Request body or form (`pipeline`) | Requires VLM models (e.g. granitedocling, granite_vision). Set `DOCLING_SERVE_ENABLE_REMOTE_SERVICES=true` if using API-based VLMs. |
| **VLM / picture description** | `vlm_pipeline_model`, `vlm_pipeline_model_local`, `vlm_pipeline_model_api`; or `picture_description_api` / `picture_description_local` with a larger model (e.g. Granite-Vision, Pixtral) | Request body or form | For API: `DOCLING_SERVE_ENABLE_REMOTE_SERVICES=true`. Pre-download or configure the chosen model. |
| **Layout** | Not configurable via API (see [Layout model selection](#layout-model-selection) below) | — | Server uses Docling default (heron). Heavier layout models require upstream support. |
| **Server / runtime** | `DOCLING_SERVE_ARTIFACTS_PATH`: directory for model weights | Environment (or CLI `--artifacts-path`) | Must match where models are downloaded or mounted. |
| | `DOCLING_SERVE_LOAD_MODELS_AT_BOOT`: `True` to load default-option models at startup | Environment | Reduces first-request latency. |
| | `DOCLING_DEVICE`: e.g. `cuda` or `cuda:0` for GPU | Environment | Speeds up layout, table, and VLM stages when GPU is available. |
| | `DOCLING_SERVE_OPTIONS_CACHE_SIZE`: increase to cache more converter instances (e.g. different option sets) | Environment | Default is 2. |

## Layout model selection

**Finding:** Layout model selection is **not** exposed in the Docling Serve API.

- **docling-jobkit** `ConvertDocumentsOptions` does not include any layout-related field (no `layout_options`, `layout_model_spec`, or format-specific pipeline options).
- When building `PdfPipelineOptions` from the request, jobkit sets OCR, table structure, picture description, and related flags but **never** sets `layout_options`. Docling therefore uses its default layout options.
- In **Docling**, `PdfPipelineOptions` has a `layout_options` attribute (type `BaseLayoutOptions`) with a `model_spec` (e.g. `LayoutModelConfig`). The default is the **heron** layout model (`docling-project/docling-layout-heron`). Docling also provides other layout model specs (e.g. `DOCLING_LAYOUT_EGRET_XLARGE`, `DOCLING_LAYOUT_EGRET_LARGE`, `DOCLING_LAYOUT_EGRET_MEDIUM`, `DOCLING_LAYOUT_HERON_101`, `DOCLING_LAYOUT_V2`) that could be used for heavier or different accuracy/speed trade-offs, but these are not selectable via the current jobkit or docling-serve API.

**Implications:**

- Today, the layout model is fixed to the Docling default (heron). To use a different layout model (e.g. egret-xlarge for higher accuracy), you would need either:
  1. A change in **docling-jobkit** to expose layout model selection in `ConvertDocumentsOptions` and to set `PdfPipelineOptions.layout_options` (e.g. from a new request field), and optionally a corresponding change in **docling-serve** to document and expose that field in the API and UI, or
  2. A server-level override (e.g. environment or config that jobkit/docling-serve use to set default layout options), which does not exist today.

**Optional follow-up:** Open a feature request or PR in docling-jobkit to add a layout model spec or layout options to the convert options, then document and expose it in docling-serve if desired.

## Model download and deployment

### Standard model names (docling-tools)

The command `docling-tools models download` accepts the following model names (no layout variants):

- `layout` — default layout model (heron)
- `tableformer`
- `code_formula`
- `picture_classifier`
- `smolvlm`, `granitedocling`, `granitedocling_mlx`, `smoldocling`, `smoldocling_mlx`, `granite_vision`
- `rapidocr`, `easyocr`

For high-accuracy setups, use at least: `layout`, `tableformer`, and (if needed) `code_formula`, `picture_classifier`, and the VLM/picture models you plan to use (e.g. `granite_vision`, `smolvlm`). The single `layout` download installs the **default** layout model (heron) only.

### Heavier layout models (Hugging Face)

docling-tools does not currently support layout **variants** (e.g. egret-xlarge) as separate model names. To use a different layout model from Hugging Face (e.g. for higher accuracy), you can:

1. Use the generic Hugging Face download command provided by docling-tools:
   ```sh
   docling-tools models download-hf-repo docling-project/docling-layout-egret-xlarge -o /path/to/artifacts
   ```
   This downloads the model into a folder under the given output directory. The layout model is then loaded by Docling when its default or configured `layout_options.model_spec` points to that repo. Because the API does not currently allow changing the layout model spec, using a different layout artifact would still require a custom build of docling-jobkit (or Docling) that sets a different default or reads layout choice from config.

2. Until layout selection is exposed, “high accuracy” layout in practice means relying on the default heron model and ensuring it is present in `DOCLING_SERVE_ARTIFACTS_PATH` (e.g. by running `docling-tools models download layout -o <artifacts_path>`).

### Deployment

- Set **`DOCLING_SERVE_ARTIFACTS_PATH`** to the directory that contains the downloaded (or mounted) models. For cluster deployments, use a PVC and a Job to run `docling-tools models download ...` (and optionally `download-hf-repo` for extra repos) into that volume, then mount the same volume into the Docling Serve deployment. See [Handling models](./models.md) and the [deployment examples](./deployment.md) (e.g. `docling-model-cache-job.yaml`, `docling-model-cache-deployment.yaml`).
- For GPU, set **`DOCLING_DEVICE`** (e.g. `cuda` or `cuda:0`). Note: TableFormer has limited or no MPS support on some platforms.

## Summary

- **Configurable today for higher accuracy:** table mode (`accurate`), OCR engine (e.g. `auto` or tesseract), PDF backend (`dlparse_v4`), pipeline (`vlm` when needed), and VLM/picture model choice via request options; server-side artifacts path, device, and cache size via environment.
- **Not configurable via API:** layout model variant. The layout stage uses Docling’s default (heron). Heavier layout models would require upstream (jobkit/Docling) support and, if desired, exposure in docling-serve.
- **Model artifacts:** Use `docling-tools models download` (and optionally `download-hf-repo`) so that the chosen models are present in `DOCLING_SERVE_ARTIFACTS_PATH`; see [Handling models](./models.md) for deployment patterns.
