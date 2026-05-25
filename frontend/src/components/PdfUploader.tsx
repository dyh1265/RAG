interface PdfUploaderProps {
  onUpload: (file: File) => void;
  ingesting: boolean;
}

export function PdfUploader({ onUpload, ingesting }: PdfUploaderProps) {
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onUpload(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file?.type === "application/pdf") onUpload(file);
  };

  return (
    <div className="upload-zone">
      <div
        className={`drop-area ${ingesting ? "drop-area-busy" : ""}`}
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
      >
        {ingesting ? (
          <>
            <div className="spinner" aria-hidden />
            <p>Ingesting PDF…</p>
            <p className="hint">Parsing, chunking, and indexing vectors</p>
          </>
        ) : (
          <>
            <div className="drop-icon">↑</div>
            <p className="drop-title">Upload a PDF to get started</p>
            <p className="hint">Drag and drop or choose a file</p>
            <label className="btn btn-primary">
              Choose PDF
              <input
                type="file"
                accept="application/pdf"
                hidden
                onChange={handleChange}
              />
            </label>
          </>
        )}
      </div>
    </div>
  );
}
