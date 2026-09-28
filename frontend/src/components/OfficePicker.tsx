import { useEffect, useRef, useState } from "react";
import { Building, Check, ChevronsUpDown, CornerUpLeft, Landmark, MapPin, Network } from "lucide-react";
import type { Me, OfficeBrief } from "../lib/types";

const DEPTH: Record<string, number> = { department: 0, wing: 1, circle: 2, division: 3, subdivision: 4 };
const ICON: Record<string, any> = { department: Landmark, wing: Landmark, circle: Network, division: Building, subdivision: MapPin };

/** Sidebar control: which office's data is on screen. Senior officers can drill into any unit below them. */
export default function OfficePicker({ me, onPick }: { me: Me; onPick: (o: OfficeBrief) => void }) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const toggle = () => {
    // the sidebar scrolls, so the menu is placed with fixed coordinates to escape its clipping
    const r = box.current?.getBoundingClientRect();
    if (r) setPos(window.innerWidth > 900 ? { top: r.bottom + 6, left: r.left } : { top: r.bottom + 6, left: 8 });
    setOpen(!open);
  };
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, [open]);

  const cur = me.office;
  const Icon = ICON[cur.level] || Building;
  const canSwitch = me.offices.length > 1;
  const away = cur.id !== me.home.id;
  const base = DEPTH[me.home.level] ?? 0;

  return (
    <div className={`opick ${open ? "open" : ""}`} ref={box}>
      <button type="button" className="opick-btn" disabled={!canSwitch} onClick={toggle}
        aria-haspopup="listbox" aria-expanded={open} title={canSwitch ? "Change which office you are looking at" : undefined}>
        <span className="opick-ic"><Icon size={16} /></span>
        <span className="opick-txt">
          <span className="opick-lvl">{away ? "Viewing" : `My ${cur.level_label}`}</span>
          <span className="opick-name">{cur.name}</span>
        </span>
        {canSwitch && <ChevronsUpDown size={15} className="opick-chev" />}
      </button>
      {away && (
        <button type="button" className="opick-back" onClick={() => onPick(me.home)}>
          <CornerUpLeft size={12} /> Back to {me.home.name}
        </button>
      )}
      {open && (
        <div className="opick-menu" role="listbox" style={pos ? { top: pos.top, left: pos.left } : undefined}>
          <div className="opick-head">Look at the data of…</div>
          {me.offices.map((o) => {
            const I = ICON[o.level] || Building;
            const on = o.id === cur.id;
            return (
              <button key={o.id} type="button" role="option" aria-selected={on}
                className={`opick-item ${on ? "on" : ""}`} style={{ paddingLeft: 10 + ((DEPTH[o.level] ?? 0) - base) * 14 }}
                onClick={() => { setOpen(false); if (!on) onPick(o); }}>
                <I size={14} className="opick-iic" />
                <span className="flex-1 min-w-0">
                  <span className="opick-iname">{o.name}</span>
                  <span className="opick-isub">{o.level_label}{o.talukas.length ? ` · ${o.talukas.join(", ")}` : o.id === me.home.id ? " · your office" : ""}</span>
                </span>
                {on && <Check size={15} />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
