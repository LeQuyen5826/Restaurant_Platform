import { useEffect, useState } from "react";
import { DishPhoto } from "../../components/PublicLayout";
import { Chili } from "../../components/ui";
import { api, vnd, type PubMenu } from "../../lib/api";

export default function MenuPage() {
  const [menu, setMenu] = useState<PubMenu | null>(null);
  const [err, setErr] = useState("");
  const [veg, setVeg] = useState(false);
  const [avoid, setAvoid] = useState<Set<string>>(new Set());
  useEffect(() => { api<PubMenu>("/public/menu").then(setMenu).catch((e) => setErr(e.message)); }, []);

  const all = new Map<string, string>();
  menu?.sections.forEach((s) => s.dishes.forEach((d) => d.allergens.forEach((a) => all.set(a.code, a.name))));
  const toggle = (c: string) => setAvoid((p) => { const n = new Set(p); n.has(c) ? n.delete(c) : n.add(c); return n; });
  const show = (d: PubMenu["sections"][0]["dishes"][0]) => (!veg || d.is_vegetarian) && !d.allergens.some((a) => avoid.has(a.code));
  const sections = menu?.sections.map((s) => ({ ...s, dishes: s.dishes.filter(show) })).filter((s) => s.dishes.length) ?? [];

  return (
    <div className="wrap page">
      <h1 className="page-title">Món ăn</h1>
      <p className="muted lead-sm">Thực đơn hôm nay. Món có thể hết trong ngày, bảng giá đã gồm thuế.</p>
      {err && <p className="form-error" role="alert">{err}</p>}
      {!menu && !err && <p className="muted">Đang tải thực đơn…</p>}
      {menu && (
        <>
          <section className="filters" aria-label="Lọc món">
            <button className={`chip ${veg ? "chip-on" : ""}`} aria-pressed={veg} onClick={() => setVeg(!veg)}>Món chay</button>
            <span className="filters-label">Tránh:</span>
            {[...all].map(([c, n]) => (
              <button key={c} className={`chip ${avoid.has(c) ? "chip-on" : ""}`} aria-pressed={avoid.has(c)} onClick={() => toggle(c)}>{n.replace(/ \(.*\)/, "")}</button>
            ))}
          </section>
          {sections.length === 0 && <p className="muted">Không có món nào phù hợp với bộ lọc.</p>}
          <div className="menu-body">
            <nav className="board-nav" aria-label="Danh mục">{sections.map((s) => <a key={s.name} href={`#sec-${s.name}`}>{s.name}</a>)}</nav>
            <div>
              {sections.map((s) => (
                <section key={s.name} id={`sec-${s.name}`} className="sec">
                  <h2>{s.name}</h2>
                  <ul className="mrows">
                    {s.dishes.map((d) => (
                      <li key={d.id} className={`mrow ${d.is_available ? "" : "soldout"}`}>
                        <DishPhoto src={d.image_url} name={d.name} className="mrow-photo" />
                        <div className="mrow-body">
                          <div className="dish-line">
                            <span className="dish-name">{d.name}<Chili n={d.spiciness} />{d.is_vegetarian && <span className="veg">chay</span>}</span>
                            <span className="leader" aria-hidden="true" />
                            <span className="dish-price">{d.is_available ? vnd(d.price_vnd) : "Hết món"}</span>
                          </div>
                          {d.description && <p className="dish-desc">{d.description}</p>}
                          {d.allergens.length > 0 && <p className="dish-allergens"><span className="muted">Chứa:</span> {d.allergens.map((a) => a.name.replace(/ \(.*\)/, "")).join(", ")}</p>}
                        </div>
                      </li>
                    ))}
                  </ul>
                </section>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
