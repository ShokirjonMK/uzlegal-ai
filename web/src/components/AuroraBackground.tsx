/**
 * Aurora fon — mesh gradient asos va uchta suzuvchi pastel blob.
 *
 * Faqat bezak: sichqoncha hodisalarini ushlamaydi va `aria-hidden` tufayli
 * ekran oʻqiguchga koʻrinmaydi. Uslublar `globals.css` da, `.aurora` boʻlimida.
 * `layout.tsx` da bir marta chiziladi — sahifadan sahifaga oʻtganda
 * animatsiya boshidan qayta boshlanmaydi.
 */
export function AuroraBackground() {
  return (
    <div className="aurora" aria-hidden="true">
      <span className="aurora-blob aurora-blob-1" />
      <span className="aurora-blob aurora-blob-2" />
      <span className="aurora-blob aurora-blob-3" />
    </div>
  );
}
