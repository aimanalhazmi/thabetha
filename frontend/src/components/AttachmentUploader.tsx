import { FileText, Image as ImageIcon, RotateCcw, Upload, X } from 'lucide-react';
import { useRef } from 'react';
import { t } from '../lib/i18n';
import type { Language, ReceiptUploadItem } from '../lib/types';
import { RECEIPT_ACCEPT, RECEIPT_IMAGE_MAX_EDGE, RECEIPT_MAX_BYTES, RECEIPT_WARN_BYTES } from '../lib/types';

interface Props {
  language: Language;
  items: ReceiptUploadItem[];
  onItemsChange: (items: ReceiptUploadItem[]) => void;
  disabled?: boolean;
  onRetry?: (item: ReceiptUploadItem) => void;
}

export function AttachmentUploader({ language, items, onItemsChange, disabled, onRetry }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const tr = (key: Parameters<typeof t>[1]) => t(language, key);

  async function addFiles(fileList: FileList | null) {
    if (!fileList) return;
    const next = await Promise.all(Array.from(fileList).map((file) => buildUploadItem(file, language)));
    onItemsChange([...items, ...next]);
    if (inputRef.current) inputRef.current.value = '';
  }

  function removeItem(id: string) {
    const item = items.find((candidate) => candidate.id === id);
    if (item?.previewUrl) URL.revokeObjectURL(item.previewUrl);
    onItemsChange(items.filter((candidate) => candidate.id !== id));
  }

  return (
    <div className="receipt-uploader">
      <div className="receipt-uploader-header">
        <div>
          <strong>{tr('receiptUpload')}</strong>
          <span>{tr('receiptUploadHint')}</span>
        </div>
        <button type="button" className="ghost-button receipt-add-button" disabled={disabled} onClick={() => inputRef.current?.click()}>
          <Upload size={16} />
          <span>{tr('receiptAdd')}</span>
        </button>
        <input
          ref={inputRef}
          type="file"
          accept={RECEIPT_ACCEPT}
          multiple
          hidden
          onChange={(event) => void addFiles(event.target.files)}
        />
      </div>

      {items.length > 0 && (
        <div className="receipt-upload-list">
          {items.map((item) => (
            <div key={item.id} className={`receipt-upload-row ${item.status}`}>
              <div className="receipt-thumb" aria-hidden="true">
                {item.previewUrl ? <img src={item.previewUrl} alt="" /> : item.contentType === 'application/pdf' ? <FileText size={18} /> : <ImageIcon size={18} />}
              </div>
              <div className="receipt-upload-meta">
                <strong>{item.name}</strong>
                <span>{formatBytes(item.size)}</span>
                {item.warning && <span className="receipt-warning">{item.warning}</span>}
                {item.error && <span className="receipt-error">{item.error}</span>}
              </div>
              <div className="receipt-upload-actions">
                {item.status === 'uploading' && <span className="receipt-status">{tr('receiptUploading')}</span>}
                {item.status === 'uploaded' && <span className="receipt-status success">{tr('receiptUploaded')}</span>}
                {item.status === 'failed' && onRetry && (
                  <button type="button" className="ghost-button" onClick={() => onRetry(item)}>
                    <RotateCcw size={15} />
                    <span>{tr('receiptRetry')}</span>
                  </button>
                )}
                {item.status !== 'uploading' && (
                  <button type="button" className="icon-button" aria-label={tr('receiptRemove')} onClick={() => removeItem(item.id)}>
                    <X size={15} />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

async function buildUploadItem(file: File, language: Language): Promise<ReceiptUploadItem> {
  const contentType = file.type || 'application/octet-stream';
  const id = typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
  const isReceiptType = contentType === 'application/pdf' || contentType.startsWith('image/');
  const base = {
    id,
    file,
    uploadFile: file,
    name: file.name,
    size: file.size,
    contentType,
  };

  if (!isReceiptType) {
    return { ...base, status: 'failed', error: t(language, 'receiptUnsupported') };
  }
  if (file.size > RECEIPT_MAX_BYTES) {
    return { ...base, status: 'failed', error: t(language, 'receiptTooLarge') };
  }

  const uploadFile = contentType.startsWith('image/') ? await resizeImage(file) : file;
  const warning = file.size >= RECEIPT_WARN_BYTES ? t(language, 'receiptLargeWarning') : undefined;
  const previewUrl = contentType.startsWith('image/') ? URL.createObjectURL(uploadFile) : undefined;
  return { ...base, uploadFile, status: warning ? 'warning' : 'ready', warning, previewUrl };
}

async function resizeImage(file: File): Promise<File> {
  const bitmap = await createImageBitmap(file).catch(() => null);
  if (!bitmap) return file;
  const longestEdge = Math.max(bitmap.width, bitmap.height);
  if (longestEdge <= RECEIPT_IMAGE_MAX_EDGE) return file;

  const scale = RECEIPT_IMAGE_MAX_EDGE / longestEdge;
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  const context = canvas.getContext('2d');
  if (!context) return file;
  context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);

  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, file.type || 'image/jpeg', 0.86));
  if (!blob) return file;
  return new File([blob], file.name, { type: file.type || 'image/jpeg', lastModified: file.lastModified });
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
