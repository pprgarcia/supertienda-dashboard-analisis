'use client';
import React, { useState } from 'react';
import { Package, Users, Globe, FileText } from 'lucide-react';
import DashboardView from '@/components/DashboardView';
import DiscountImpactView from '@/components/DiscountImpactView';
import ProductsView from '@/components/ProductsView';
import CustomersView from '@/components/CustomersView'; 
import CountriesView from '@/components/CountriesView'; 
import ConclusionsView from '@/components/ConclusionsView';


interface SidebarBtnProps {
  icon: React.ReactElement;
  label: string;
  active: boolean;
  onClick: () => void;
}

export default function MainApp() {
  const [activeTab, setActiveTab] = useState('dashboard');

  const titles: Record<string, string> = {
    dashboard: "Panel de Control",
    discounts: "Impacto de Descuentos",
    products: "Auditoría de Productos",
    clients: "Análisis de Clientes",
    countries: "Global Analytics",
    conclusions: "Reporte de Conclusiones"
  };

  return (
    <div className="flex min-h-screen bg-slate-50 font-sans">
      {/* SIDEBAR */}
      <aside className="w-64 bg-white border-r border-slate-200 hidden md:flex flex-col fixed h-full z-20">
        <div className="p-6 border-b border-slate-100 font-black text-xl text-purple-600 tracking-tighter">
          SuperTienda Pro
        </div>
        <nav className="flex-1 p-4 space-y-2">
          <SidebarBtn icon={<Package/>} label="Dashboard" active={activeTab === 'dashboard'} onClick={() => setActiveTab('dashboard')} />
          <SidebarBtn icon={<FileText/>} label="Descuentos" active={activeTab === 'discounts'} onClick={() => setActiveTab('discounts')} />
          <SidebarBtn icon={<Package/>} label="Productos" active={activeTab === 'products'} onClick={() => setActiveTab('products')} />
          <SidebarBtn icon={<Users/>} label="Clientes" active={activeTab === 'clients'} onClick={() => setActiveTab('clients')} />
          <SidebarBtn icon={<Globe/>} label="Países" active={activeTab === 'countries'} onClick={() => setActiveTab('countries')} />
          <SidebarBtn icon={<FileText/>} label="Conclusiones" active={activeTab === 'conclusions'} onClick={() => setActiveTab('conclusions')} />

        </nav>
      </aside>

      {/* CONTENIDO PRINCIPAL */}
      <main className="flex-1 md:ml-64 p-8 overflow-x-hidden flex flex-col min-h-screen">
        <header className="flex justify-between items-center mb-10 shrink-0">
          <div>
            <h1 className="text-3xl font-extrabold text-slate-800 tracking-tight">
              {titles[activeTab]}
            </h1>
            <p className="text-slate-500 mt-1 text-sm font-medium italic">
              {activeTab === 'clients' ? "Segmentación y rentabilidad de cartera" : "Segmentación por Grupos de Descuento en la Utilidad Neta"}
            </p>
          </div>

        </header>

        {/* VISTAS DINÁMICAS */}
        <div className="flex-1">
          {activeTab === 'dashboard' && <DashboardView />}
          {activeTab === 'discounts' && <DiscountImpactView />} 
          {activeTab === 'products' && <ProductsView />}
          {activeTab === 'countries' && <CountriesView />}
          {activeTab === 'conclusions' && <ConclusionsView />}

          
          {/* 2. CAMBIO AQUÍ: Reemplazamos el div por el componente real */}

          {activeTab === 'clients' && <CustomersView />}

        </div>
      </main>
    </div>
  );
}

// SidebarBtn se mantiene igual (ya lo tienes corregido sin any)
function SidebarBtn({ icon, label, active, onClick }: SidebarBtnProps) {
  return (
    <button onClick={onClick} className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${active ? 'bg-purple-600 text-white shadow-lg shadow-purple-200' : 'text-slate-500 hover:bg-slate-50'}`}>
      {React.cloneElement(icon as React.ReactElement<{ size?: number }>, { size: 20 })}
      <span className="font-bold text-sm">{label}</span>
    </button>
  );
}