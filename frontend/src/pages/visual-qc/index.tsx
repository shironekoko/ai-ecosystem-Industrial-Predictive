import React from 'react';
import { PageHeader } from '../../components/common/PageHeader';
import { EmptyState } from '../../components/common/EmptyState';
import { Camera, ZoomIn, ZoomOut, Maximize, Map, Check, X, AlertTriangle, Lock } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export default function VisualQC() {
  const { isAuthenticated } = useAuth();
  const steps = [
    { label: 'Upload/Stream' },
    { label: 'AI Analysis' },
    { label: 'Inspector Review' },
    { label: 'Decision' }
  ];

  return (
    <div className="space-y-6">
      <PageHeader 
        title="Visual Quality Inspection" 
        subtitle="PatchCore anomaly detection and inspector verification console" 
      />

      {/* Workflow Step Indicator */}
      <div className="bg-white p-6 border border-gray-200 rounded-lg shadow-sm">
        <div className="flex items-center justify-between">
          {steps.map((step, index) => (
            <React.Fragment key={step.label}>
              <div className="flex flex-col items-center flex-1">
                <div className="w-8 h-8 rounded-full border-2 border-gray-300 flex items-center justify-center text-gray-400 font-medium mb-2">
                  {index + 1}
                </div>
                <span className="text-sm font-medium text-gray-500">{step.label}</span>
              </div>
              {index < steps.length - 1 && (
                <div className="flex-1 h-0.5 bg-gray-200"></div>
              )}
            </React.Fragment>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* Inspection Viewport */}
        <div className="col-span-12 lg:col-span-7 flex flex-col space-y-4">
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm flex-1 flex flex-col overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gray-50">
              <h3 className="font-semibold text-gray-800">Inspection Viewport</h3>
              <div className="flex space-x-2">
                <button disabled className="p-1.5 text-gray-400 rounded hover:bg-gray-200 disabled:opacity-50">
                  <ZoomIn className="w-4 h-4" />
                </button>
                <button disabled className="p-1.5 text-gray-400 rounded hover:bg-gray-200 disabled:opacity-50">
                  <ZoomOut className="w-4 h-4" />
                </button>
                <button disabled className="p-1.5 text-gray-400 rounded hover:bg-gray-200 disabled:opacity-50">
                  <Maximize className="w-4 h-4" />
                </button>
                <div className="w-px h-5 bg-gray-300 mx-1 self-center"></div>
                <button disabled className="flex items-center space-x-1 px-2 py-1.5 text-xs font-medium text-gray-400 rounded border border-gray-200 disabled:opacity-50">
                  <Map className="w-3.5 h-3.5 mr-1" />
                  Heatmap Overlay
                </button>
              </div>
            </div>
            
            <div className="flex-1 p-6 bg-gray-50 flex items-center justify-center min-h-[400px]">
              <div className="w-full h-full border-2 border-dashed border-gray-300 rounded-lg flex items-center justify-center bg-white">
                <EmptyState 
                  icon={Camera}
                  title="No images loaded" 
                  description="Connect MinIO to stream inspection images." 
                />
              </div>
            </div>
          </div>
        </div>

        {/* Diagnostic Panel */}
        <div className="col-span-12 lg:col-span-5 flex flex-col space-y-6">
          <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
            <h3 className="font-semibold text-gray-800 mb-4 border-b border-gray-100 pb-2">Analysis Results</h3>
            
            <div className="space-y-6">
              <div>
                <div className="flex justify-between items-center mb-1">
                  <span className="text-sm font-medium text-gray-600">Anomaly Score</span>
                  <span className="text-sm font-semibold text-gray-400">0.00</span>
                </div>
                <div className="w-full bg-gray-100 rounded-full h-2">
                  <div className="bg-gray-300 h-2 rounded-full" style={{ width: '0%' }}></div>
                </div>
              </div>

              <div className="space-y-3 pt-2">
                <div className="flex justify-between items-center text-sm">
                  <span className="text-gray-500">Classification</span>
                  <span className="font-medium text-gray-400">--</span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-gray-500">Lot Number</span>
                  <span className="font-medium text-gray-400">--</span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-gray-500">Part SKU</span>
                  <span className="font-medium text-gray-400">--</span>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
            <h3 className="font-semibold text-gray-800 mb-4 border-b border-gray-100 pb-2">Actions</h3>
            
            <div className="flex space-x-3 mb-3">
              <button disabled className="flex-1 flex items-center justify-center space-x-2 py-2.5 px-4 bg-emerald-50 text-emerald-600 font-medium rounded-lg border border-emerald-200 opacity-50 cursor-not-allowed">
                <Check className="w-4 h-4" />
                <span>Accept</span>
              </button>
              <button disabled className="flex-1 flex items-center justify-center space-x-2 py-2.5 px-4 bg-red-50 text-red-600 font-medium rounded-lg border border-red-200 opacity-50 cursor-not-allowed">
                <X className="w-4 h-4" />
                <span>Reject</span>
              </button>
            </div>
            
            <button disabled className="w-full flex items-center justify-center space-x-2 py-2.5 px-4 bg-white text-amber-600 font-medium rounded-lg border border-amber-200 opacity-50 cursor-not-allowed">
              <AlertTriangle className="w-4 h-4" />
              <span>Override AI</span>
            </button>

            {!isAuthenticated && (
              <p className="text-[11px] text-amber-600 mt-3 pt-2 border-t border-gray-100 flex items-center gap-1.5">
                <Lock className="w-3.5 h-3.5 shrink-0" />
                <span>Sign in required to execute QC decisions or overrides.</span>
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export const VisualQcPage = VisualQC;
