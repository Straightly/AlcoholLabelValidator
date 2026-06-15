# Local Bottle Intake

Place your bottle photographs and filled JSON manifests in this folder.

1. Copy the relevant `.json.example` file to a filename ending in `.json`.
2. Give every submission and application a new unique identifier.
3. Replace the sample field values.
4. Copy the referenced images into this same folder.
5. Make every `image_filenames` entry exactly match an image filename.
6. In the application, select `Reset Demo Data`, then `Process Sample Intake`.

Filled `.json` files and bottle photographs in this folder are ignored by Git
because this is a private working area. The `.json.example` templates are not
processed by the application.

After reviewing photographs for visible personal information and removing
EXIF/GPS metadata, copy the final submission-safe evaluation set to
`fixtures/evaluation-real/`. Files in that directory are committed to Git.

Supported image extensions are `.png`, `.jpg`, `.jpeg`, `.webp`, and `.svg`.
Each image must be 15 MB or smaller.
