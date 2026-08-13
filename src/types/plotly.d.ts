/**
 * plotly.js-dist-min ships no type declarations. We use exactly three of its
 * functions and pass configuration objects that Plotly validates at runtime, so
 * a minimal ambient declaration is the honest shape here — a fuller
 * hand-written type would imply a compile-time guarantee we do not have.
 */
declare module "plotly.js-dist-min" {
  const Plotly: {
    newPlot: (
      el: HTMLElement,
      data: unknown[],
      layout?: unknown,
      config?: unknown,
    ) => Promise<unknown>;
    react: (
      el: HTMLElement,
      data: unknown[],
      layout?: unknown,
      config?: unknown,
    ) => Promise<unknown>;
    purge: (el: HTMLElement) => void;
  };
  export default Plotly;
}
