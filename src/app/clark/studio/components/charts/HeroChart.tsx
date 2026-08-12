"use client";

import React, { useEffect, useRef } from "react";
import { createChart, IChartApi, ISeriesApi, ColorType, CrosshairMode } from "lightweight-charts";
import { useChartColors } from "../../chartColors";

interface ChartDataPoint {
  t: string;
  v: number;
}

interface HeroChartProps {
  data: ChartDataPoint[];
  height?: number;
}

export default function HeroChart({ data, height = 400 }: HeroChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  // lightweight-charts parses colors in JS, so it needs literal hexes
  // (a CSS var throws "Cannot parse color"). Rebuilds on theme change.
  const c = useChartColors();

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Create chart instance
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: c.textDim,
        fontFamily: "Inter, sans-serif",
      },
      grid: {
        vertLines: { color: c.grid },
        horzLines: { color: c.grid },
      },
      crosshair: {
        mode: CrosshairMode.Magnet,
        vertLine: {
          color: c.accent,
          width: 1,
          style: 3, // dashed
          labelBackgroundColor: c.accent,
        },
        horzLine: {
          color: c.accent,
          width: 1,
          style: 3,
          labelBackgroundColor: c.accent,
        },
      },
      rightPriceScale: {
        borderVisible: false,
      },
      timeScale: {
        borderVisible: false,
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: true,
      },
      handleScale: {
        axisPressedMouseMove: true,
        mouseWheel: true,
        pinch: true,
      },
      width: chartContainerRef.current.clientWidth,
      height: height,
    });

    chartRef.current = chart;

    // Create Area series
    const areaSeries = chart.addAreaSeries({
      lineColor: c.accent,
      topColor: c.accent + "66",
      bottomColor: c.accent + "00",
      lineWidth: 2,
      priceFormat: {
        type: "price",
        precision: 2,
        minMove: 0.01,
      },
    });

    seriesRef.current = areaSeries;

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [height, c]);

  useEffect(() => {
    if (seriesRef.current && data.length > 0) {
      const formattedData = data
        .map((d) => {
          let timeVal: any = d.t;
          if (typeof d.t === "string" && !/^\d{4}-\d{2}-\d{2}$/.test(d.t)) {
            const parsed = Math.floor(new Date(d.t).getTime() / 1000);
            if (!isNaN(parsed) && parsed > 0) {
              timeVal = parsed;
            }
          }
          return { time: timeVal, value: d.v };
        })
        .sort((a, b) => {
          const tA = typeof a.time === "number" ? a.time : new Date(a.time).getTime();
          const tB = typeof b.time === "number" ? b.time : new Date(b.time).getTime();
          return tA - tB;
        });

      // Deduplicate items with the exact same timestamp to prevent lightweight-charts errors
      const deduped: typeof formattedData = [];
      for (const item of formattedData) {
        if (deduped.length === 0 || deduped[deduped.length - 1].time !== item.time) {
          deduped.push(item);
        } else {
          deduped[deduped.length - 1] = item;
        }
      }

      seriesRef.current.setData(deduped);
      chartRef.current?.timeScale().fitContent();
    }
  }, [data]);

  return <div ref={chartContainerRef} className="w-full relative rounded-lg overflow-hidden" />;
}
