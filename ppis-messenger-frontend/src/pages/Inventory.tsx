import { FormEvent, useCallback, useEffect, useState } from "react";
import { ArrowLeft, Boxes, RefreshCw, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import {
  InventoryCategory,
  InventoryItem,
  createInventoryCategory,
  createInventoryItem,
  createInventoryTransaction,
  getInventorySummary,
  listInventoryCategories,
  listInventoryItems,
  updateInventoryItem,
} from "../lib/api";

const inputClass = "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-lime-500 focus:ring-2 focus:ring-lime-100";
const buttonClass = "rounded-lg bg-lime-600 px-4 py-2 text-sm font-semibold text-white hover:bg-lime-700 disabled:cursor-not-allowed disabled:opacity-50";
const secondaryButtonClass = "rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50";
const errorMessage = (error: unknown, fallback: string) => error instanceof Error ? error.message : fallback;
type Tab = "items" | "categories";
type ItemForm = { name: string; category_id: string; unit: string; reorder_level: string; unit_cost: string; location: string; status: InventoryItem["status"] };
const emptyForm: ItemForm = { name: "", category_id: "", unit: "unit", reorder_level: "0", unit_cost: "0", location: "", status: "active" };

export default function Inventory() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("items");
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [categories, setCategories] = useState<InventoryCategory[]>([]);
  const [summary, setSummary] = useState<{ total_items: number; total_stock_value: number; low_stock_count: number } | null>(null);
  const [search, setSearch] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [status, setStatus] = useState("");
  const [lowStock, setLowStock] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [itemForm, setItemForm] = useState(emptyForm);
  const [categoryName, setCategoryName] = useState("");
  const [editingId, setEditingId] = useState<number>();
  const [stockAction, setStockAction] = useState<{ id: number; type: "in" | "out" | "adjust" }>();
  const [stockValue, setStockValue] = useState("");
  const [stockNote, setStockNote] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const loadCategories = useCallback(async () => { const data = await listInventoryCategories(); setCategories(data.categories || []); }, []);
  const loadItems = useCallback(async () => {
    const [data, summaryData] = await Promise.all([
      listInventoryItems({ search, category_id: categoryId ? Number(categoryId) : undefined, status, low_stock: lowStock, page, limit: 50 }),
      getInventorySummary(),
    ]);
    setItems(data.items || []); setTotal(data.total || 0); setSummary(summaryData);
  }, [categoryId, lowStock, page, search, status]);
  useEffect(() => { loadCategories().catch((loadError: unknown) => setError(errorMessage(loadError, "Unable to load categories"))); }, [loadCategories]);
  useEffect(() => { loadItems().catch((loadError: unknown) => setError(errorMessage(loadError, "Unable to load inventory"))); }, [loadItems]);
  const submitItem = async (event: FormEvent) => {
    event.preventDefault();
    try {
      const body = { name: itemForm.name, category_id: itemForm.category_id ? Number(itemForm.category_id) : undefined, unit: itemForm.unit, reorder_level: Number(itemForm.reorder_level), unit_cost: Number(itemForm.unit_cost), location: itemForm.location, status: itemForm.status };
      if (editingId) await updateInventoryItem(editingId, body); else await createInventoryItem(body);
      setItemForm(emptyForm); setEditingId(undefined); setNotice(editingId ? "Item updated." : "Item created."); await loadItems();
    } catch (saveError) { setError(errorMessage(saveError, "Item could not be saved")); }
  };
  const submitCategory = async (event: FormEvent) => { event.preventDefault(); try { await createInventoryCategory(categoryName); setCategoryName(""); setNotice("Category created."); await loadCategories(); } catch (categoryError) { setError(errorMessage(categoryError, "Category could not be created")); } };
  const submitStock = async (event: FormEvent) => {
    event.preventDefault(); if (!stockAction) return;
    try {
      const body = stockAction.type === "adjust" ? { txn_type: "adjust" as const, new_quantity: Number(stockValue), note: stockNote } : { txn_type: stockAction.type, quantity: Number(stockValue), note: stockNote };
      await createInventoryTransaction(stockAction.id, body); setStockAction(undefined); setStockValue(""); setStockNote(""); setNotice("Stock updated."); await loadItems();
    } catch (stockError) { setError(errorMessage(stockError, "Stock could not be updated")); }
  };
  const edit = (item: InventoryItem) => setItemForm({ name: item.name, category_id: item.category_id ? String(item.category_id) : "", unit: item.unit, reorder_level: String(item.reorder_level), unit_cost: String(item.unit_cost), location: item.location, status: item.status });
  const updateForm = (key: keyof ItemForm, value: string) => setItemForm({ ...itemForm, [key]: value });
  const pages = Math.max(1, Math.ceil(total / 50));
  return <div className="min-h-screen bg-slate-50 text-slate-900"><header className="border-b border-slate-200 bg-white"><div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-4 sm:px-6 lg:px-8"><button onClick={() => navigate("/erp")} className="rounded-lg p-2 hover:bg-slate-100" aria-label="Back to ERP"><ArrowLeft size={20} /></button><Boxes className="text-lime-600" /><div><p className="text-xs font-semibold uppercase tracking-widest text-lime-600">School ERP</p><h1 className="text-xl font-bold">Inventory</h1></div><button onClick={() => { void loadItems(); void loadCategories(); }} className="ml-auto rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label="Refresh"><RefreshCw size={18} /></button></div></header><main className="mx-auto max-w-7xl px-4 py-7 sm:px-6 lg:px-8"><h2 className="text-2xl font-bold">Inventory management</h2><p className="mb-6 text-sm text-slate-500">Track stock, costs, categories and reorder levels.</p>{error && <div className="mb-4 flex items-center justify-between rounded-lg bg-red-50 p-3 text-sm text-red-700"><span>{error}</span><button onClick={() => setError("")}><X size={16} /></button></div>}{notice && <div className="mb-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">{notice}</div>}<div className="mb-6 grid gap-4 sm:grid-cols-3"><Stat label="Total items" value={String(summary?.total_items || 0)} /><Stat label="Stock value" value={`₹${(summary?.total_stock_value || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`} /><Stat label="Low stock" value={String(summary?.low_stock_count || 0)} /></div><nav className="mb-6 flex gap-1 rounded-xl border border-slate-200 bg-white p-1">{([["items", "Items"], ["categories", "Categories"]] as Array<[Tab, string]>).map(([value, label]) => <button key={value} onClick={() => setTab(value)} className={`rounded-lg px-4 py-2 text-sm font-semibold ${tab === value ? "bg-lime-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{label}</button>)}</nav>{tab === "items" ? <section className="grid gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]"><div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="mb-4 grid gap-3 sm:grid-cols-4"><input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search name or SKU" className={inputClass} /><select value={categoryId} onChange={(event) => { setCategoryId(event.target.value); setPage(1); }} className={inputClass}><option value="">All categories</option>{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select><select value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }} className={inputClass}><option value="">All statuses</option><option value="active">Active</option><option value="inactive">Inactive</option></select><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={lowStock} onChange={(event) => { setLowStock(event.target.checked); setPage(1); }} /> Low stock</label></div><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b text-slate-500"><th className="px-2 py-2">Item</th><th className="px-2 py-2">Category</th><th className="px-2 py-2">Stock</th><th className="px-2 py-2">Cost</th><th /></tr></thead><tbody>{items.map((item) => <tr key={item.id} className={`border-b last:border-0 ${item.quantity <= item.reorder_level ? "bg-lime-50" : ""}`}><td className="px-2 py-3"><b>{item.name}</b><span className="block text-xs text-slate-500">{item.sku}</span></td><td className="px-2 py-3">{item.category_name || "—"}</td><td className="px-2 py-3">{item.quantity} {item.unit}<span className="block text-xs text-slate-500">Reorder at {item.reorder_level}</span></td><td className="px-2 py-3">₹{item.unit_cost.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td><td className="px-2 py-3"><div className="flex flex-wrap gap-1"><button onClick={() => { edit(item); setEditingId(item.id); }} className={secondaryButtonClass}>Edit</button><button onClick={() => setStockAction({ id: item.id, type: "in" })} className={secondaryButtonClass}>In</button><button onClick={() => setStockAction({ id: item.id, type: "out" })} className={secondaryButtonClass}>Out</button><button onClick={() => setStockAction({ id: item.id, type: "adjust" })} className={secondaryButtonClass}>Adjust</button></div></td></tr>)}</tbody></table></div><div className="mt-4 flex items-center justify-between text-sm text-slate-500"><span>{total} items</span><div className="flex items-center gap-2"><button disabled={page <= 1} onClick={() => setPage(page - 1)} className={secondaryButtonClass}>Previous</button><span>Page {page} of {pages}</span><button disabled={page >= pages} onClick={() => setPage(page + 1)} className={secondaryButtonClass}>Next</button></div></div></div><div className="space-y-5"><form onSubmit={submitItem} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="mb-4 font-semibold">{editingId ? "Edit item" : "Add item"}</h3><div className="space-y-3"><label className="text-sm font-medium">Name<input required value={itemForm.name} onChange={(event) => updateForm("name", event.target.value)} className={`${inputClass} mt-1`} /></label><div className="grid gap-3 sm:grid-cols-2"><label className="text-sm font-medium">Category<select value={itemForm.category_id} onChange={(event) => updateForm("category_id", event.target.value)} className={`${inputClass} mt-1`}><option value="">None</option>{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label><label className="text-sm font-medium">Unit<input value={itemForm.unit} onChange={(event) => updateForm("unit", event.target.value)} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium">Reorder level<input type="number" min="0" value={itemForm.reorder_level} onChange={(event) => updateForm("reorder_level", event.target.value)} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium">Unit cost (₹)<input type="number" min="0" step="0.01" value={itemForm.unit_cost} onChange={(event) => updateForm("unit_cost", event.target.value)} className={`${inputClass} mt-1`} /></label></div><label className="text-sm font-medium">Location<input value={itemForm.location} onChange={(event) => updateForm("location", event.target.value)} className={`${inputClass} mt-1`} /></label><label className="text-sm font-medium">Status<select value={itemForm.status} onChange={(event) => updateForm("status", event.target.value as InventoryItem["status"])} className={`${inputClass} mt-1`}><option value="active">Active</option><option value="inactive">Inactive</option></select></label></div><div className="mt-4 flex gap-2"><button className={buttonClass}>{editingId ? "Update item" : "Add item"}</button>{editingId && <button type="button" onClick={() => { setEditingId(undefined); setItemForm(emptyForm); }} className={secondaryButtonClass}>Cancel</button>}</div></form>{stockAction && <form onSubmit={submitStock} className="rounded-xl border border-lime-200 bg-lime-50 p-5 shadow-sm"><h3 className="mb-3 font-semibold">Stock {stockAction.type === "adjust" ? "adjustment" : stockAction.type === "in" ? "in" : "out"}</h3><input required type="number" min="0" value={stockValue} onChange={(event) => setStockValue(event.target.value)} placeholder={stockAction.type === "adjust" ? "New absolute quantity" : "Quantity"} className={inputClass} /><input value={stockNote} onChange={(event) => setStockNote(event.target.value)} placeholder="Note (optional)" className={`${inputClass} mt-3`} /><div className="mt-3 flex gap-2"><button className={buttonClass}>Save stock</button><button type="button" onClick={() => setStockAction(undefined)} className={secondaryButtonClass}>Cancel</button></div></form>}</div></section> : <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]"><div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="mb-4 font-semibold">Categories</h3>{categories.map((category) => <div key={category.id} className="flex justify-between border-b py-3 text-sm last:border-0"><span>{category.name}</span><span className="text-slate-500">{category.item_count || 0} items</span></div>)}</div><form onSubmit={submitCategory} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="mb-4 font-semibold">Create category</h3><input required value={categoryName} onChange={(event) => setCategoryName(event.target.value)} placeholder="Category name" className={inputClass} /><button className={`${buttonClass} mt-4`}>Create category</button></form></section>}</main></div>;
}

function Stat({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><p className="text-sm text-slate-500">{label}</p><p className="mt-1 text-2xl font-bold">{value}</p></div>;
}
