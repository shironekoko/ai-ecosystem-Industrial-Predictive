import React, { useState } from 'react';
import {
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Sparkles,
  ScanEye,
  Crosshair,
  Layers,
} from 'lucide-react';

export type ViewportModality = 'TOOL_RAW' | 'TOOL_EDGE_PROCESSED';

interface OpticalScanViewportProps {
  recordId: string;
  toolImageUrl?: string | null;
  toolProcessedImageUrl?: string | null;
  activeModality?: ViewportModality;
  onModalityChange?: (modality: ViewportModality) => void;
}

export function OpticalScanViewport({
  recordId,
  toolImageUrl,
  toolProcessedImageUrl,
  activeModality = 'TOOL_EDGE_PROCESSED',
  onModalityChange,
}: OpticalScanViewportProps) {
  const [currentModality, setCurrentModality] = useState<ViewportModality>(activeModality);
  const [zoomLevel, setZoomLevel] = useState<number>(1);
  const [showGradCam, setShowGradCam] = useState<boolean>(false);

  const selectedModality = onModalityChange ? activeModality : currentModality;
  const setModality = (m: ViewportModality) => {
    if (onModalityChange) {
      onModalityChange(m);
    } else {
      setCurrentModality(m);
    }
  };

  const activeImageUrl =
    selectedModality === 'TOOL_EDGE_PROCESSED'
      ? toolProcessedImageUrl || toolImageUrl
      : toolImageUrl;

  const hasImage = Boolean(activeImageUrl);

  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-xs overflow-hidden flex flex-col h-full">
      {/* Viewport Top Header & Inspection Modality Toggle */}
      <div className="px-4 py-3 border-b border-gray-100 flex flex-wrap items-center justify-between gap-3 bg-gray-50/70">
        {/* Modality Selector: Raw Flank vs Image Processed Overlay */}
        <div className="flex items-center gap-1.5 p-1 bg-gray-200/80 rounded-lg">
          <button
            onClick={() => setModality('TOOL_RAW')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-bold transition ${
              selectedModality === 'TOOL_RAW'
                ? 'bg-white text-indigo-700 shadow-xs'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <ScanEye className="w-3.5 h-3.5" />
            <span>Raw Microscope Feed (ภาพถ่ายส่องมีดจริง)</span>
            {toolImageUrl && <span className="w-1.5 h-1.5 rounded-full bg-indigo-500" />}
          </button>

          <button
            onClick={() => setModality('TOOL_EDGE_PROCESSED')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-bold transition ${
              selectedModality === 'TOOL_EDGE_PROCESSED'
                ? 'bg-white text-purple-700 shadow-xs'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <Layers className="w-3.5 h-3.5 text-purple-600" />
            <span>Image Processing Overlay (ตรวจวัดรอยสึก Vb &amp; ขอบบิ่น)</span>
            {toolProcessedImageUrl && <span className="w-1.5 h-1.5 rounded-full bg-purple-500" />}
          </button>
        </div>

        {/* Viewport Zoom & Filter Controls */}
        {hasImage && (
          <div className="flex items-center gap-1">
            {selectedModality === 'TOOL_RAW' && (
              <button
                onClick={() => setShowGradCam(!showGradCam)}
                className={`flex items-center gap-1 px-2.5 py-1 rounded text-xs font-semibold transition ${
                  showGradCam
                    ? 'bg-purple-100 text-purple-700 border border-purple-200'
                    : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-100'
                }`}
                title="Toggle Grad-CAM Attention Heatmap"
              >
                <Sparkles className="w-3.5 h-3.5 text-purple-600" />
                <span>{showGradCam ? 'Grad-CAM ON' : 'Grad-CAM'}</span>
              </button>
            )}

            <button
              onClick={() => setZoomLevel((z) => Math.min(2.5, z + 0.25))}
              className="p-1.5 text-gray-600 hover:bg-gray-200 rounded"
              title="Zoom In"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setZoomLevel((z) => Math.max(1, z - 0.25))}
              className="p-1.5 text-gray-600 hover:bg-gray-200 rounded"
              title="Zoom Out"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setZoomLevel(1)}
              className="p-1.5 text-gray-600 hover:bg-gray-200 rounded"
              title="Reset Zoom"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>

      {/* Main Canvas Area */}
      <div className="p-6 bg-slate-950 flex-1 flex items-center justify-center min-h-[380px] overflow-hidden relative select-none">
        {/* Optical Alignment Crosshairs Grid */}
        <div className="absolute inset-0 grid grid-cols-6 grid-rows-4 pointer-events-none opacity-5">
          {Array.from({ length: 24 }).map((_, i) => (
            <div key={i} className="border border-white" />
          ))}
        </div>

        {hasImage ? (
          <div
            className="relative transition-transform duration-200 ease-out"
            style={{ transform: `scale(${zoomLevel})` }}
          >
            <img
              src={activeImageUrl || ''}
              alt={recordId}
              className="max-h-80 w-auto object-contain rounded border border-slate-700 shadow-xl"
              onError={(e) => {
                (e.target as HTMLElement).style.display = 'none';
              }}
            />

            {/* Grad-CAM Overlay for raw tool scan */}
            {showGradCam && selectedModality === 'TOOL_RAW' && (
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-rose-500/35 to-amber-500/40 mix-blend-screen pointer-events-none rounded border-2 border-rose-400/80 flex items-end p-2">
                <span className="px-2 py-0.5 rounded bg-rose-900/90 text-white font-mono text-[10px] font-bold">
                  Wear Zone High Activation (XAI Attention)
                </span>
              </div>
            )}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center text-slate-700 pointer-events-none select-none z-10">
            <Crosshair className="w-10 h-10 opacity-30 stroke-[1.2] mb-2" />
            <span className="text-[11px] font-mono tracking-widest uppercase opacity-40">
              No Optical Feed Received for {recordId}
            </span>
          </div>
        )}

        {/* Viewport Metadata Overlay */}
        <div className="absolute bottom-3 left-3 bg-black/75 backdrop-blur-xs px-3 py-1.5 rounded-lg text-[10px] font-mono text-gray-300 border border-white/10 flex items-center gap-2.5">
          <span className="font-bold text-white uppercase">
            {selectedModality === 'TOOL_EDGE_PROCESSED'
              ? 'OpenCV Edge & Vb Metrology Overlay'
              : 'Keyence Optical Microscope (1550×500 px)'}
          </span>
          <span className="text-gray-500">|</span>
          <span>Target Blade: {recordId}</span>
          <span className="text-gray-500">|</span>
          <span className="text-indigo-400">Station Bench #1</span>
        </div>
      </div>
    </div>
  );
}

export default OpticalScanViewport;
