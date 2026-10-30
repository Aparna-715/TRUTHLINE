/**
 * TRUTHLINE — matrix rain backdrop
 * ==========================================================================
 * A canvas of falling glyph columns, drawn behind everything at low alpha so
 * it reads as atmosphere rather than noise. Sits above the body gradient but
 * below the content; the scanline + vignette layers live in theme.css on top.
 *
 * Deliberately throttled: ~22fps, capped columns, and it pauses when the tab
 * is hidden. A background effect should never cost frames from the analysis.
 */

import { useEffect, useRef } from 'react';

const GLYPHS = 'アカサタナハマヤラワｦｧｨｩｪｫｬｭｮｯｱｲｳｴｵ0123456789ABCDEF<>/\\|=+-*'.split('');

export default function MatrixRain() {
  const ref = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let width = 0;
    let height = 0;
    let columns: number[] = [];
    let frame: number | null = null;
    let last = 0;

    const FONT_SIZE = 15;
    const SPEED_MS = 46; // ~22fps

    const resize = () => {
      width = window.innerWidth;
      height = window.innerHeight;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      const count = Math.ceil(width / FONT_SIZE);
      columns = Array.from({ length: count }, () =>
        Math.floor(Math.random() * (height / FONT_SIZE)),
      );
      ctx.font = `${FONT_SIZE}px ui-monospace, monospace`;
    };

    const draw = (t: number) => {
      frame = requestAnimationFrame(draw);
      if (t - last < SPEED_MS) return;
      last = t;

      // Fade previous frame instead of clearing — this is what creates trails.
      ctx.fillStyle = 'rgba(4, 10, 6, 0.10)';
      ctx.fillRect(0, 0, width, height);

      ctx.font = `${FONT_SIZE}px ui-monospace, monospace`;

      for (let i = 0; i < columns.length; i++) {
        const x = i * FONT_SIZE;
        const y = columns[i] * FONT_SIZE;
        const glyph = GLYPHS[(Math.random() * GLYPHS.length) | 0];

        // Head glyph is bright, the rest of the column fades behind it.
        ctx.fillStyle = 'rgba(0, 255, 156, 0.30)';
        ctx.fillText(glyph, x, y);

        // Occasionally leave a brighter leading character.
        if (Math.random() > 0.985) {
          ctx.fillStyle = 'rgba(160, 255, 210, 0.55)';
          ctx.fillText(glyph, x, y);
        }

        columns[i] = y > height && Math.random() > 0.975 ? 0 : columns[i] + 1;
      }
    };

    resize();
    window.addEventListener('resize', resize);
    frame = requestAnimationFrame(draw);

    const onVisibility = () => {
      if (document.hidden) {
        if (frame) cancelAnimationFrame(frame);
        frame = null;
      } else if (!frame) {
        frame = requestAnimationFrame(draw);
      }
    };
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      window.removeEventListener('resize', resize);
      document.removeEventListener('visibilitychange', onVisibility);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <canvas
      ref={ref}
      aria-hidden="true"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 0,
        pointerEvents: 'none',
        opacity: 0.5,
      }}
    />
  );
}
