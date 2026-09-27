import React, { useState } from 'react';
import { PageHeader } from '../../components/common/PageHeader';
import { EmptyState } from '../../components/common/EmptyState';
import { UploadCloud, Package, Search, Lock } from 'lucide-react';
import { PartCatalogItem } from '../../types';
import { useAuth } from '../../context/AuthContext';

export default function Inventory() {
  const { isAuthenticated } = useAuth();
  const [parts, setParts] = useState<PartCatalogItem[]>([]);
  
  const [category, setCategory] = useState('Screw (General)');
  const [sku, setSku] = useState('');
  const [name, setName] = useState('');
  const [specs, setSpecs] = useState('');
  const [search, setSearch] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!sku || !name) return;
    
    const newPart: PartCatalogItem = {
      sku,
      name,
      category,
      specifications: specs,
      minioObjectPath: `s3://industrial-datasets/screw/${sku.toLowerCase()}.png`,
      stockQty: 0,
      updatedAt: new Date().toISOString()
    };

    setParts(prev => [...prev, newPart]);
    setSku('');
    setName('');
    setSpecs('');
  };

  const filteredParts = parts.filter(p => 
    p.sku.toLowerCase().includes(search.toLowerCase()) || 
    p.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <PageHeader 
        title="Parts Catalog" 
        subtitle="Screw component registry and MinIO object storage" 
      />

      <div className="grid grid-cols-12 gap-6">
        {/* Registration Form */}
        <div className="col-span-12 lg:col-span-5 flex flex-col">
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
              <h3 className="font-semibold text-gray-800">Register New Component</h3>
            </div>
            
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
                <select 
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  value={category}
                  onChange={e => setCategory(e.target.value)}
                >
                  <option>Screw (General)</option>
                  <option>Screw - Thread Type</option>
                  <option>Screw - Head Type</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Part SKU</label>
                <input 
                  type="text" 
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="e.g. SCR-M4-16-PH"
                  value={sku}
                  onChange={e => setSku(e.target.value)}
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Component Name</label>
                <input 
                  type="text" 
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="e.g. M4 × 16mm Phillips Head Screw"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Specifications</label>
                <input 
                  type="text" 
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="e.g. DIN 965, A2 Stainless Steel"
                  value={specs}
                  onChange={e => setSpecs(e.target.value)}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Reference Image</label>
                <div className="mt-1 flex justify-center px-6 pt-5 pb-6 border-2 border-gray-300 border-dashed rounded-md hover:bg-gray-50 cursor-pointer">
                  <div className="space-y-1 text-center">
                    <UploadCloud className="mx-auto h-8 w-8 text-gray-400" />
                    <div className="flex text-sm text-gray-600 justify-center">
                      <span className="relative cursor-pointer bg-transparent rounded-md font-medium text-blue-600 hover:text-blue-500 focus-within:outline-none">
                        Click to upload reference image
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="pt-2">
                <button 
                  type="submit"
                  disabled={!isAuthenticated}
                  title={!isAuthenticated ? 'Sign in required to register components' : ''}
                  className={`w-full flex items-center justify-center gap-1.5 py-2.5 px-4 rounded-lg text-sm font-medium transition shadow-sm ${
                    !isAuthenticated
                      ? 'bg-gray-100 text-gray-400 border border-gray-200 cursor-not-allowed'
                      : 'bg-indigo-600 hover:bg-indigo-700 text-white'
                  }`}
                >
                  {!isAuthenticated && <Lock className="w-4 h-4" />}
                  <span>{isAuthenticated ? 'Register Component' : 'Sign In Required to Register'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>

        {/* Catalog Table */}
        <div className="col-span-12 lg:col-span-7 flex flex-col">
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden flex-1 flex flex-col">
            <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center bg-gray-50">
              <h3 className="font-semibold text-gray-800">Catalog Items</h3>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Search className="h-4 w-4 text-gray-400" />
                </div>
                <input
                  type="text"
                  placeholder="Search parts..."
                  className="pl-9 pr-3 py-1.5 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                />
              </div>
            </div>
            
            <div className="flex-1 min-h-[400px]">
              {filteredParts.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">SKU</th>
                        <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                        <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Category</th>
                        <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Stock</th>
                        <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Updated</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {filteredParts.map((part) => (
                        <tr key={part.sku}>
                          <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{part.sku}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{part.name}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{part.category}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{part.stockQty || 0}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            {new Date(part.updatedAt || '').toLocaleDateString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="h-full flex items-center justify-center p-6">
                  <EmptyState 
                    icon={Package}
                    title="No components registered" 
                    description="Use the form to add your first screw part." 
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export const InventoryPage = Inventory;

