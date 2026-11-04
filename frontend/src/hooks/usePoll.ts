import { useEffect, useRef } from "react";

/** Gọi fn ngay rồi lặp lại mỗi `ms`; tạm dừng khi tab bị ẩn. */
export function usePoll(fn: () => void | Promise<unknown>, ms: number) {
  const ref = useRef(fn);
  ref.current = fn;
  useEffect(() => {
    const run = () => { if (!document.hidden) void ref.current(); };
    run();
    const h = setInterval(run, ms);
    document.addEventListener("visibilitychange", run);
    return () => { clearInterval(h); document.removeEventListener("visibilitychange", run); };
  }, [ms]);
}
