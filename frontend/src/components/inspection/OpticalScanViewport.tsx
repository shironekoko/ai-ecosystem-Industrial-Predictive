import React, { useState } from 'react';
import {
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Sparkles,
  ScanEye,
  Crosshair,
} from 'lucide-react';

interface OpticalScanViewportProps {
  recordId: string;
  imageUrl: string | null;
}

export function OpticalScanViewport({
  recordId,
  imageUrl,
}: OpticalScanViewportProps) {
  const [zoomLevel, setZoomLevel] = useState<number>(1);
  const [showGradCam, setShowGradCam] = useState<boolean>(false);

  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden flex flex-col h-full">
      {/* Viewport Top Header */}
      <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between bg-gray-50/50">
        <div className="flex items-center gap-2">
          <ScanEye className="w-4 h-4 text-indigo-600" />
          <span className="font-bold text-xs text-gray-900 font-mono">
            {imageUrl ? `${recordId}.jpg` : 'OPTICAL_FEED: STANDBY'}
          </span>
          <span className="text-[11px] text-gray-400 font-sans">
            (Flank Face Microscope · 1550×500 px)
          </span>
        </div>

        {/* Viewport Controls: Enabled ONLY when image is present */}
        {imageUrl && (
          <div className="flex items-center gap-1">
            <button
              onClick={() => setShowGradCam(!showGradCam)}
              className={`flex items-center gap-1 px-2.5 py-1 rounded text-xs font-semibold transition ${
                showGradCam
                  ? 'bg-purple-100 text-purple-700 border border-purple-200'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
              title="Toggle Explainable AI Grad-CAM Heatmap"
            >
              <Sparkles className="w-3.5 h-3.5 text-purple-600" />
              <span>{showGradCam ? 'Grad-CAM: ON' : 'Grad-CAM XAI'}</span>
            </button>

            <button
              onClick={() => setZoomLevel((z) => Math.min(2.5, z + 0.25))}
              className="p-1.5 text-gray-500 hover:bg-gray-100 rounded"
              title="Zoom In"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setZoomLevel((z) => Math.max(1, z - 0.25))}
              className="p-1.5 text-gray-500 hover:bg-gray-100 rounded"
              title="Zoom Out"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setZoomLevel(1)}
              className="p-1.5 text-gray-500 hover:bg-gray-100 rounded"
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

        {imageUrl ? (
          /* Captured Image Display */
          <div
            className="relative transition-transform duration-200 ease-out"
            style={{ transform: `scale(${zoomLevel})` }}
          >
            <img
              src={imageUrl}
              alt={recordId}
              className="max-h-72 w-auto object-contain rounded border border-slate-700 shadow-xl"
              onError={(e) => {
                (e.target as HTMLElement).style.display = 'none';
              }}
            />

            {/* Grad-CAM Attention Heatmap Overlay */}
            {showGradCam && (
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-rose-500/35 to-amber-500/40 mix-blend-screen pointer-events-none rounded border-2 border-rose-400/80 flex items-end p-2">
                <span className="px-2 py-0.5 rounded bg-rose-900/90 text-white font-mono text-[10px] font-bold">
                  Wear Zone High Activation (XAI Attention)
                </span>
              </div>
            )}
          </div>
        ) : (
          /* Clean Empty Viewport (ช่วงว่างรอรับภาพจาก API กล้องจริง - ไม่มีปุ่มหลอก) */
          <div className="flex flex-col items-center justify-center text-slate-700 pointer-events-none select-none z-10">
            <Crosshair className="w-10 h-10 opacity-30 stroke-[1.2] mb-2" />
            <span className="text-[11px] font-mono tracking-widest uppercase opacity-40">
              No Optical Feed Received
            </span>
          </div>
        )}

        {/* Viewport Metadata Overlay */}
        <div className="absolute bottom-3 left-3 bg-black/70 px-2.5 py-1 rounded text-[10px] font-mono text-gray-300 border border-white/10 flex items-center gap-2">
          <span>Scale: 100 µm ───</span>
          <span className="text-gray-500">|</span>
          <span>Station: Keyence VHX Optical Fixture</span>
        </div>
      </div>
    </div>
  );
}
