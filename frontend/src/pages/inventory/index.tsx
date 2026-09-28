import React, { useState } from 'react';
import { PageHeader } from '../../components/common/PageHeader';
import { EmptyState } from '../../components/common/EmptyState';
import { Wrench, Search, Package, Plus } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export interface CuttingToolItem {
  sku: string;
  name: string;
  category: string;
  teethCount: number;
  diameterMm: number;
  fluteLengthMm: number;
  stockQty: number;
  updatedAt: string;
}

export function InventoryPage() {
  const { isAuthenticated } = useAuth();
  const [tools, setTools] = useState<CuttingToolItem[]>([]);
  const [search, setSearch] = useState('');

  const [category, setCategory] = useState('Face Mill (4-Flute)');
  const [sku, setSku] = useState('');
  const [name, setName] = useState('');
  const [diameter, setDiameter] = useState(25);
  const [teeth, setTeeth] = useState(4);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!sku || !name) return;

    const newTool: CuttingToolItem = {
      sku,
      name,
      category,
      teethCount: teeth,
      diameterMm: diameter,
      fluteLengthMm: 45,
      stockQty: 1,
      updatedAt: new Date().toISOString(),
    };

    setTools((prev) => [...prev, newTool]);
    setSku('');
    setName('');
  };

  const filteredTools = tools.filter(
    (t) =>
      t.sku.toLowerCase().includes(search.toLowerCase()) ||
      t.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Cutting Tool Inventory & Presets"
        subtitle="Milling cutter catalog, insert specifications, and tool magazine registry"
      />

      <div className="grid grid-cols-12 gap-6">
        {/* Registration Form */}
        <div className="col-span-12 lg:col-span-5 flex flex-col">
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 bg-gray-50/50">
              <h3 className="font-semibold text-gray-900 text-sm">Register Milling Cutter Preset</h3>
            </div>

            <form onSubmit={handleSubmit} className="p-6 space-y-4 text-xs">
              <div>
                <label className="block font-medium text-gray-700 mb-1">Cutter Category</label>
                <select
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-xs bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                >
                  <option>Face Mill (4-Flute)</option>
                  <option>Solid Carbide End Mill</option>
                  <option>Ball Nose End Mill</option>
                  <option>Indexable Insert (ISO APKT)</option>
                </select>
              </div>

              <div>
                <label className="block font-medium text-gray-700 mb-1">Tool SKU / Preset ID</label>
                <input
                  type="text"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-xs font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="e.g. MILL-FM-25-4T"
                  value={sku}
                  onChange={(e) => setSku(e.target.value)}
                  required
                />
              </div>

              <div>
                <label className="block font-medium text-gray-700 mb-1">Tool Description</label>
                <input
                  type="text"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="e.g. 25mm 4-Flute High-Feed Cutter"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-gray-700 mb-1">Diameter (mm)</label>
                  <input
                    type="number"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-xs font-mono"
                    value={diameter}
                    onChange={(e) => setDiameter(Number(e.target.value))}
                    min="1"
                  />
                </div>
                <div>
                  <label className="block font-medium text-gray-700 mb-1">Flutes / Teeth</label>
                  <input
                    type="number"
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-xs font-mono"
                    value={teeth}
                    onChange={(e) => setTeeth(Number(e.target.value))}
                    min="1"
                    max="12"
                  />
                </div>
              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-lg shadow-sm transition flex items-center justify-center gap-1.5"
                >
                  <Plus className="w-4 h-4" />
                  <span>Register Tool Preset</span>
                </button>
              </div>
            </form>
          </div>
        </div>

        {/* Tools Catalog Table */}
        <div className="col-span-12 lg:col-span-7 flex flex-col">
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden flex-1 flex flex-col">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between bg-gray-50/50">
              <h3 className="font-semibold text-gray-900 text-sm">Registered Tool Spares</h3>
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search SKU..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pl-8 pr-3 py-1 border border-gray-200 rounded-lg text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>
            </div>

            {filteredTools.length === 0 ? (
              <div className="py-16 flex-1 flex items-center justify-center">
                <EmptyState
                  icon={Wrench}
                  title="No Cutting Tools in Catalog"
                  description="Register tool presets using the form or connect to toolroom ERP inventory API."
                />
              </div>
            ) : (
              <div className="overflow-x-auto flex-1">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-gray-50 text-[11px] uppercase tracking-wider text-gray-400 font-semibold border-b border-gray-100">
                    <tr>
                      <th className="px-5 py-3">SKU</th>
                      <th className="px-4 py-3">Name</th>
                      <th className="px-4 py-3">Category</th>
                      <th className="px-4 py-3">Geometry</th>
                      <th className="px-4 py-3 text-right">Stock</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {filteredTools.map((t) => (
                      <tr key={t.sku} className="hover:bg-gray-50/70 transition">
                        <td className="px-5 py-3.5 font-bold text-gray-900">{t.sku}</td>
                        <td className="px-4 py-3.5 font-sans font-medium text-gray-800">{t.name}</td>
                        <td className="px-4 py-3.5 text-gray-500">{t.category}</td>
                        <td className="px-4 py-3.5 text-gray-600">Ø{t.diameterMm}mm · {t.teethCount}T</td>
                        <td className="px-4 py-3.5 text-right font-bold text-indigo-600">{t.stockQty}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default InventoryPage;
