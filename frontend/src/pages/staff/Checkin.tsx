import { useEffect, useRef, useState, type FormEvent } from "react";
import { useToast } from "../../components/ui";
import { send } from "../../lib/api";

interface Result { session_id: string; table_code: string; customer: string | null; party_size: number; pre_ordered_items: number; service_request: string | null }

// BarcodeDetector có sẵn trên Chrome (Android, máy tính); trình duyệt khác dùng ô nhập mã.
declare global { interface Window { BarcodeDetector?: new (o: { formats: string[] }) => { detect: (v: HTMLVideoElement) => Promise<{ rawValue: string }[]> } } }

export default function Checkin() {
  const toast = useToast();
  const [code, setCode] = useState("");
  const [res, setRes] = useState<Result | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [scan, setScan] = useState(false);
  const video = useRef<HTMLVideoElement>(null);
  const canScan = typeof window !== "undefined" && !!window.BarcodeDetector && !!navigator.mediaDevices?.getUserMedia;

  const submit = async (c: string) => {
    setBusy(true); setErr(""); setRes(null);
    try { const r = await send<Result>("POST", "/floor/checkin", { code: c }); setRes(r); setCode(""); toast(`Đã check-in, mời khách vào bàn ${r.table_code}`); }
    catch (e) { setErr((e as Error).message); }
    setBusy(false);
  };
  const onSubmit = (e: FormEvent) => { e.preventDefault(); if (code.trim()) void submit(code); };

  useEffect(() => {
    if (!scan) return;
    let stop = false; let stream: MediaStream | undefined;
    (async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
        if (!video.current) return;
        video.current.srcObject = stream; await video.current.play();
        const det = new window.BarcodeDetector!({ formats: ["qr_code"] });
        while (!stop) {
          const f = await det.detect(video.current).catch(() => []);
          if (f[0]?.rawValue) { setScan(false); void submit(f[0].rawValue); return; }
          await new Promise((r) => setTimeout(r, 300));
        }
      } catch { setErr("Không mở được camera. Hãy cấp quyền camera (cần HTTPS) hoặc nhập mã bằng tay."); setScan(false); }
    })();
    return () => { stop = true; stream?.getTracks().forEach((t) => t.stop()); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scan]);

  return (
    <>
      <header className="page-head"><div><h1>Check-in khách đặt trước</h1><p className="muted">Quét mã QR trên điện thoại khách hoặc nhập mã 8 ký tự. Hệ thống mở đúng bàn đã giữ.</p></div></header>
      <section className="panel checkin">
        <form onSubmit={onSubmit} className="inline-add">
          <input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="Mã check-in, ví dụ BK7F3K9Q" aria-label="Mã check-in" autoCapitalize="characters" autoComplete="off" />
          <button className="btn" disabled={busy || !code.trim()}>Check-in</button>
        </form>
        {canScan && <p style={{ marginBottom: 14 }}><button className="btn-ghost" onClick={() => setScan(!scan)}>{scan ? "Tắt camera" : "Quét mã bằng camera"}</button></p>}
        {scan && <video ref={video} className="scanner" muted playsInline />}
        {err && <p className="form-error" role="alert">{err}</p>}
        {res && (
          <div className="result" role="status">
            <p className="eyebrow">Mời khách vào</p>
            <p className="result-table">Bàn {res.table_code}</p>
            <p>{res.customer ?? "Khách"} · {res.party_size} người</p>
            {res.pre_ordered_items > 0 && <p>Có {res.pre_ordered_items} món đặt trước, đã gửi xuống bếp.</p>}
            {res.service_request && <p className="slip-note">Yêu cầu: {res.service_request}</p>}
          </div>
        )}
      </section>
    </>
  );
}
