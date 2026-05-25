export interface LocalFolderSelection {
  name: string;
  pdfCount: number;
  files: File[];
  sampleNames: string[];
}

const STORAGE_KEY = "documind.lastLocalFolder";

export function loadLastLocalFolderName(): string | null {
  return sessionStorage.getItem(STORAGE_KEY);
}

export function saveLastLocalFolderName(name: string): void {
  sessionStorage.setItem(STORAGE_KEY, name);
}

async function collectPdfsFromDirectory(
  dir: FileSystemDirectoryHandle,
): Promise<File[]> {
  const files: File[] = [];
  for await (const [name, entry] of dir.entries()) {
    if (entry.kind === "file") {
      if (!name.toLowerCase().endsWith(".pdf")) continue;
      const file = await (entry as FileSystemFileHandle).getFile();
      files.push(new File([file], name, { type: file.type || "application/pdf" }));
    } else if (entry.kind === "directory") {
      files.push(...(await collectPdfsFromDirectory(entry as FileSystemDirectoryHandle)));
    }
  }
  return files;
}

export function folderNameFromFiles(files: File[]): string {
  for (const file of files) {
    const rel = file.webkitRelativePath || (file as File & { path?: string }).path;
    if (rel) {
      const sep = rel.includes("\\") ? "\\" : "/";
      const part = rel.split(sep)[0];
      if (part) return part;
    }
  }
  if (files.length === 1) {
    return files[0].name.replace(/\.pdf$/i, "");
  }
  return "Selected folder";
}

/** Modern folder picker (Chrome/Edge) — returns null if user cancelled. */
export async function pickFolderWithDirectoryPicker(): Promise<LocalFolderSelection | null> {
  if (!("showDirectoryPicker" in window)) {
    return null;
  }
  try {
    const handle = await window.showDirectoryPicker({ mode: "read" });
    const files = await collectPdfsFromDirectory(handle);
    return {
      name: handle.name,
      pdfCount: files.length,
      files,
      sampleNames: files.slice(0, 3).map((f) => f.name),
    };
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      return null;
    }
    throw err;
  }
}

export function selectionFromInputFiles(files: File[]): LocalFolderSelection {
  const pdfFiles = files.filter((f) => f.name.toLowerCase().endsWith(".pdf"));
  const name = folderNameFromFiles(files);
  return {
    name,
    pdfCount: pdfFiles.length,
    files: pdfFiles,
    sampleNames: pdfFiles.slice(0, 3).map((f) => f.name),
  };
}
