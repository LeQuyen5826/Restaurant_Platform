import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { Drawer, Chili, Empty, Switch, useToast } from "../../components/ui";
import { api, send, upload, vnd, type Allergen, type Category, type Dish } from "../../lib/api";

const PERIODS: [string, string][] = [["breakfast", "Sáng"], ["lunch", "Trưa"], ["dinner", "Tối"]];
const csv = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);
const blank = (): Dish => ({
  id: "", name: "", description: "", price_vnd: 0, category_id: null, image_url: null, spiciness: 0,
  is_vegetarian: false, cuisine: "", tags: [], ingredients: [], meal_periods: ["breakfast", "lunch", "dinner"],
  allergens: [], is_available: true, is_active: true,
});

export default function MenuAdmin() {
  const toast = useToast();
  const [dishes, setDishes] = useState<Dish[]>([]);
  const [cats, setCats] = useState<Category[]>([]);
  const [allergens, setAllergens] = useState<Allergen[]>([]);
  const [filter, setFilter] = useState<string>("all");
  const [edit, setEdit] = useState<Dish | null>(null);
  const [showCats, setShowCats] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    try {
      const [d, c, a] = await Promise.all([
        api<Dish[]>("/menu/dishes"), api<Category[]>("/menu/categories"), api<Allergen[]>("/allergens"),
      ]);
      setDishes(d); setCats(c); setAllergens(a);
    } catch (e) { toast((e as Error).message, "err"); }
    setLoaded(true);
  }, [toast]);
  useEffect(() => { load(); }, [load]);

  const catName = useMemo(() => new Map(cats.map((c) => [c.id, c.name])), [cats]);
  const shown = dishes.filter((d) => filter === "all" || (filter === "none" ? !d.category_id : d.category_id === filter));

  const toggleAvail = async (d: Dish, v: boolean) => {
    try { await send("PATCH", `/menu/dishes/${d.id}/availability`, { is_available: v }); toast(v ? `${d.name} đã còn món` : `${d.name} đã hết món`); load(); }
    catch (e) { toast((e as Error).message, "err"); }
  };

  return (
    <>
      <header className="page-head">
        <div><h1>Thực đơn</h1><p className="muted">{dishes.length} món · {cats.length} danh mục</p></div>
        <div className="head-actions">
          <button className="btn-ghost" onClick={() => setShowCats(true)}>Danh mục</button>
          <button className="btn" onClick={() => setEdit(blank())}>Thêm món</button>
        </div>
      </header>

      <div className="pills" role="tablist" aria-label="Lọc theo danh mục">
        {[["all", "Tất cả"], ...cats.map((c) => [c.id, c.name]), ["none", "Chưa phân loại"]].map(([id, n]) => (
          <button key={id} role="tab" aria-selected={filter === id} className={`pill ${filter === id ? "on" : ""}`} onClick={() => setFilter(id)}>{n}</button>
        ))}
      </div>

      {loaded && shown.length === 0 && (
        <Empty title="Chưa có món nào ở đây" hint="Thêm món đầu tiên để khách có thể xem thực đơn.">
          <button className="btn" onClick={() => setEdit({ ...blank(), category_id: cats.some((c) => c.id === filter) ? filter : null })}>Thêm món</button>
        </Empty>
      )}

      {shown.length > 0 && (
        <div className="grid-table" role="table" aria-label="Danh sách món">
          <div className="gt-head" role="row">
            <span>Món</span><span>Danh mục</span><span className="num">Giá</span><span>Còn món</span><span />
          </div>
          {shown.map((d) => (
            <div key={d.id} role="row" className={`gt-row ${d.is_active ? "" : "dim"}`}>
              <span className="gt-main">
                {d.image_url && <img className="thumb" src={d.image_url} alt="" />}
                <b>{d.name}</b><Chili n={d.spiciness} />
                {d.is_vegetarian && <span className="veg">chay</span>}
                {!d.is_active && <span className="tag-hidden">đang ẩn</span>}
                {d.allergens.length > 0 && <small className="muted">Chứa: {d.allergens.map((a) => allergens.find((x) => x.code === a)?.name.replace(/ \(.*\)/, "") ?? a).join(", ")}</small>}
              </span>
              <span className="muted">{(d.category_id && catName.get(d.category_id)) || "Chưa phân loại"}</span>
              <span className="num">{vnd(d.price_vnd)}</span>
              <span><Switch on={d.is_available} onChange={(v) => toggleAvail(d, v)} label={`${d.name} còn món`} /></span>
              <span className="gt-act"><button className="btn-quiet" onClick={() => setEdit(d)}>Sửa</button></span>
            </div>
          ))}
        </div>
      )}

      {edit && <DishForm dish={edit} cats={cats} allergens={allergens} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); load(); }} />}
      {showCats && <CategoryPanel cats={cats} onClose={() => setShowCats(false)} onChanged={load} />}
    </>
  );
}

function DishForm({ dish, cats, allergens, onClose, onSaved }: {
  dish: Dish; cats: Category[]; allergens: Allergen[]; onClose: () => void; onSaved: () => void;
}) {
  const toast = useToast();
  const [d, setD] = useState<Dish>(dish);
  const [tags, setTags] = useState(dish.tags.join(", "));
  const [ing, setIng] = useState(dish.ingredients.join(", "));
  const [busy, setBusy] = useState(false);
  const isNew = !dish.id;
  const set = <K extends keyof Dish>(k: K, v: Dish[K]) => setD((p) => ({ ...p, [k]: v }));
  const flip = (k: "allergens" | "meal_periods", v: string) =>
    set(k, d[k].includes(v) ? d[k].filter((x) => x !== v) : [...d[k], v]);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    if (d.meal_periods.length === 0) return toast("Chọn ít nhất một bữa ăn", "err");
    setBusy(true);
    const body = { ...d, tags: csv(tags), ingredients: csv(ing), description: d.description || null, cuisine: d.cuisine || null };
    try {
      await (isNew ? send("POST", "/menu/dishes", body) : send("PUT", `/menu/dishes/${d.id}`, body));
      toast(isNew ? `Đã thêm ${d.name}` : `Đã lưu ${d.name}`);
      onSaved();
    } catch (err) { toast((err as Error).message, "err"); setBusy(false); }
  };

  const remove = async () => {
    if (!confirm(`Xóa món "${d.name}"? Nếu món đã từng được gọi, hãy dùng "Ẩn khỏi thực đơn" thay vì xóa.`)) return;
    try { await send("DELETE", `/menu/dishes/${d.id}`); toast(`Đã xóa ${d.name}`); onSaved(); }
    catch (err) { toast((err as Error).message, "err"); }
  };

  return (
    <Drawer title={isNew ? "Thêm món" : "Sửa món"} onClose={onClose}>
      <form className="form" onSubmit={save}>
        <label className="field"><span>Tên món</span><input value={d.name} onChange={(e) => set("name", e.target.value)} required autoFocus /></label>
        <div className="two">
          <label className="field"><span>Giá (đồng)</span><input type="number" min={0} step={1000} value={d.price_vnd} onChange={(e) => set("price_vnd", Number(e.target.value))} required /></label>
          <label className="field"><span>Danh mục</span>
            <select value={d.category_id ?? ""} onChange={(e) => set("category_id", e.target.value || null)}>
              <option value="">Chưa phân loại</option>
              {cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
        </div>
        <fieldset className="field"><legend>Ảnh món</legend>
          {isNew ? <p className="muted">Lưu món trước, sau đó mở lại để thêm ảnh.</p> : (
            <div className="img-edit">
              {d.image_url ? <img src={d.image_url} alt={`Ảnh ${d.name}`} /> : <div className="photo-ph"><span>{d.name.charAt(0).toUpperCase() || "?"}</span></div>}
              <div>
                <label className="btn-ghost file-btn">{d.image_url ? "Đổi ảnh" : "Tải ảnh lên"}
                  <input type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={async (e) => {
                    const f = e.target.files?.[0]; e.target.value = "";
                    if (!f) return;
                    try { const r = await upload<{ image_url: string }>(`/menu/dishes/${d.id}/image`, f); set("image_url", r.image_url); toast("Đã cập nhật ảnh"); }
                    catch (err) { toast((err as Error).message, "err"); }
                  }} /></label>
                {d.image_url && <button type="button" className="btn-quiet" onClick={async () => { try { await send("DELETE", `/menu/dishes/${d.id}/image`); set("image_url", null); toast("Đã gỡ ảnh"); } catch (err) { toast((err as Error).message, "err"); } }}>Gỡ ảnh</button>}
                <small className="muted">JPG, PNG hoặc WebP, tối đa 3 MB.</small>
              </div>
            </div>
          )}
        </fieldset>
        <label className="field"><span>Mô tả</span><textarea rows={3} value={d.description ?? ""} onChange={(e) => set("description", e.target.value)} /></label>

        <fieldset className="field"><legend>Độ cay</legend>
          <div className="seg">
            {["Không cay", "Nhẹ", "Vừa", "Rất cay"].map((l, i) => (
              <button type="button" key={l} className={d.spiciness === i ? "on" : ""} aria-pressed={d.spiciness === i} onClick={() => set("spiciness", i)}>{l}</button>
            ))}
          </div>
        </fieldset>

        <fieldset className="field"><legend>Chứa chất gây dị ứng</legend>
          <div className="chips">
            {allergens.map((a) => (
              <button type="button" key={a.code} className={`chip ${d.allergens.includes(a.code) ? "chip-on" : ""}`} aria-pressed={d.allergens.includes(a.code)} onClick={() => flip("allergens", a.code)}>{a.name.replace(/ \(.*\)/, "")}</button>
            ))}
          </div>
          <small className="muted">Khách bị dị ứng sẽ không được gợi ý các món đã đánh dấu. Hãy đánh dấu cẩn thận.</small>
        </fieldset>

        <fieldset className="field"><legend>Phục vụ vào bữa</legend>
          <div className="chips">
            {PERIODS.map(([v, l]) => (
              <button type="button" key={v} className={`chip ${d.meal_periods.includes(v) ? "chip-on" : ""}`} aria-pressed={d.meal_periods.includes(v)} onClick={() => flip("meal_periods", v)}>{l}</button>
            ))}
          </div>
        </fieldset>

        <div className="two">
          <label className="field"><span>Ẩm thực</span><input value={d.cuisine ?? ""} onChange={(e) => set("cuisine", e.target.value)} placeholder="Việt, Thái, Âu…" /></label>
          <label className="check"><input type="checkbox" checked={d.is_vegetarian} onChange={(e) => set("is_vegetarian", e.target.checked)} /> Món chay</label>
        </div>
        <label className="field"><span>Nguyên liệu chính</span><input value={ing} onChange={(e) => setIng(e.target.value)} placeholder="tôm, bún, rau thơm" /><small className="muted">Cách nhau bằng dấu phẩy. Dùng để gợi ý món giống khẩu vị.</small></label>
        <label className="field"><span>Thẻ mô tả</span><input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="nước, nướng, thanh đạm" /></label>

        <div className="toggles">
          <label className="check"><input type="checkbox" checked={d.is_available} onChange={(e) => set("is_available", e.target.checked)} /> Còn món</label>
          <label className="check"><input type="checkbox" checked={!d.is_active} onChange={(e) => set("is_active", !e.target.checked)} /> Ẩn khỏi thực đơn</label>
        </div>

        <footer className="form-foot">
          {!isNew && <button type="button" className="btn-danger" onClick={remove}>Xóa món</button>}
          <span className="grow" />
          <button type="button" className="btn-ghost" onClick={onClose}>Hủy</button>
          <button className="btn" disabled={busy}>{busy ? "Đang lưu" : "Lưu món"}</button>
        </footer>
      </form>
    </Drawer>
  );
}

function CategoryPanel({ cats, onClose, onChanged }: { cats: Category[]; onClose: () => void; onChanged: () => void }) {
  const toast = useToast();
  const [name, setName] = useState("");
  const run = async (fn: () => Promise<unknown>, ok: string) => {
    try { await fn(); toast(ok); onChanged(); } catch (e) { toast((e as Error).message, "err"); }
  };
  return (
    <Drawer title="Danh mục món" onClose={onClose}>
      <form className="inline-add" onSubmit={(e) => { e.preventDefault(); if (!name.trim()) return; run(() => send("POST", "/menu/categories", { name, sort_order: cats.length }), `Đã thêm ${name}`).then(() => setName("")); }}>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Tên danh mục mới" aria-label="Tên danh mục mới" />
        <button className="btn">Thêm</button>
      </form>
      {cats.length === 0 ? <Empty title="Chưa có danh mục" hint="Ví dụ: Khai vị, Món chính, Tráng miệng, Đồ uống." /> : (
        <ul className="cat-list">
          {cats.map((c) => (
            <li key={c.id}>
              <input defaultValue={c.name} aria-label={`Tên danh mục ${c.name}`}
                onBlur={(e) => e.target.value.trim() && e.target.value !== c.name && run(() => send("PUT", `/menu/categories/${c.id}`, { name: e.target.value, sort_order: c.sort_order }), "Đã đổi tên")} />
              <button className="btn-quiet" onClick={() => confirm(`Xóa danh mục "${c.name}"? Các món bên trong sẽ chuyển sang "Chưa phân loại".`) && run(() => send("DELETE", `/menu/categories/${c.id}`), `Đã xóa ${c.name}`)}>Xóa</button>
            </li>
          ))}
        </ul>
      )}
    </Drawer>
  );
}
