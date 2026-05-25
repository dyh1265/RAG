import { useCallback, useEffect, useRef, useState } from "react";
import type { FolderLoadProgress } from "../types";
import { FolderLoadStatusBar } from "./FolderLoadStatusBar";
import {
  loadLastLocalFolderName,
  pickFolderWithDirectoryPicker,
  saveLastLocalFolderName,
  selectionFromInputFiles,
  type LocalFolderSelection,
} from "../utils/localFolderPicker";

interface BulkIndexPanelProps {
  onSelectLocalFolder: (files: File[], folderName?: string) => void;
  indexing: boolean;
  folderProgress: FolderLoadProgress | null;
  disabled: boolean;
  uploadDoneToken?: number;
}

export function BulkIndexPanel({
  onSelectLocalFolder,
  indexing,
  folderProgress,
  disabled,
  uploadDoneToken,
}: BulkIndexPanelProps) {
  const [folderError, setFolderError] = useState<string | null>(null);
  const [localSelection, setLocalSelection] = useState<LocalFolderSelection | null>(null);
  const [lastUploadedFolder, setLastUploadedFolder] = useState<string | null>(
    () => loadLastLocalFolderName(),
  );
  const [picking, setPicking] = useState(false);
  const folderInputRef = useRef<HTMLInputElement>(null);

  const applySelection = useCallback((selection: LocalFolderSelection) => {
    saveLastLocalFolderName(selection.name);
    setLastUploadedFolder(null);
    if (selection.pdfCount === 0) {
      setLocalSelection(selection);
      setFolderError(`"${selection.name}" has no PDF files.`);
      return;
    }
    setFolderError(null);
    setLocalSelection(selection);
  }, []);

  useEffect(() => {
    if (uploadDoneToken && uploadDoneToken > 0) {
      if (localSelection?.name) {
        setLastUploadedFolder(localSelection.name);
      }
      setLocalSelection(null);
    }
  }, [uploadDoneToken]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSelectFolder = async () => {
    setFolderError(null);
    setPicking(true);
    try {
      const fromPicker = await pickFolderWithDirectoryPicker();
      if (fromPicker !== null) {
        applySelection(fromPicker);
        return;
      }
      folderInputRef.current?.click();
    } catch (e) {
      setFolderError((e as Error).message);
    } finally {
      setPicking(false);
    }
  };

  const handleFolderInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = e.target.files;
    e.target.value = "";
    if (!fileList?.length) return;
    applySelection(selectionFromInputFiles(Array.from(fileList)));
  };

  const uploadLocalFolder = () => {
    if (!localSelection?.files.length) return;
    onSelectLocalFolder(localSelection.files, localSelection.name);
  };

  const clearLocalSelection = () => {
    setLocalSelection(null);
    setFolderError(null);
  };

  const displayName = localSelection?.name ?? lastUploadedFolder;
  const displayCount = localSelection?.pdfCount;
  const displaySamples = localSelection?.sampleNames ?? [];
  const localProgress = folderProgress?.source === "local" ? folderProgress : null;

  return (
    <section className="sidebar-section bulk-index">
      <h3>Index folder</h3>

      <div className="local-folder-block">
        <div
          className={
            displayName ? "local-folder-display selected" : "local-folder-display empty"
          }
        >
          <div className="local-folder-display-row">
            <span className="local-folder-icon">📂</span>
            <div className="local-folder-text">
              {displayName ? (
                <>
                  <strong title={displayName}>{displayName}</strong>
                  {localSelection ? (
                    <span>
                      {displayCount} PDF{displayCount === 1 ? "" : "s"} ready
                      {displaySamples.length > 0 && (
                        <> · {displaySamples.join(", ")}{displayCount! > 3 ? "…" : ""}</>
                      )}
                    </span>
                  ) : (
                    <span className="local-folder-done">Uploaded — see Recent documents</span>
                  )}
                </>
              ) : (
                <>
                  <strong>No folder selected</strong>
                  <span>Click Select folder below</span>
                </>
              )}
            </div>
          </div>
        </div>

        <button
          type="button"
          className="btn btn-ghost btn-sm select-folder-btn"
          disabled={disabled || indexing || picking}
          onClick={() => void handleSelectFolder()}
        >
          {picking ? "Opening…" : "Select folder…"}
        </button>
        <input
          ref={folderInputRef}
          className="folder-input-hidden"
          type="file"
          multiple
          disabled={disabled || indexing}
          onChange={handleFolderInput}
          {...({ webkitdirectory: "", directory: "" } as React.InputHTMLAttributes<HTMLInputElement>)}
        />

        {localSelection && localSelection.pdfCount > 0 && (
          <div className="local-folder-actions">
            <button
              type="button"
              className="btn btn-primary btn-sm bulk-btn"
              disabled={disabled || indexing}
              onClick={uploadLocalFolder}
            >
              {indexing && localProgress ? "Uploading…" : "Upload & index (Celery)"}
            </button>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              disabled={indexing}
              onClick={clearLocalSelection}
            >
              Clear
            </button>
          </div>
        )}

        {localProgress && <FolderLoadStatusBar progress={localProgress} />}

        {folderError && <p className="dir-error local-folder-error">{folderError}</p>}
      </div>
    </section>
  );
}
