"use client";

import React, { useEffect, useRef } from "react";
import { createChart, IChartApi, ISeriesApi, ColorType, CrosshairMode } from "lightweight-charts";

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

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Create chart instance
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#a1a1aa", // zinc-400
        fontFamily: "Inter, sans-serif",
      },
      grid: {
        vertLines: { color: "rgba(255, 255, 255, 0.05)" },
        horzLines: { color: "rgba(255, 255, 255, 0.05)" },
      },
      crosshair: {
        mode: CrosshairMode.Magnet,
        vertLine: {
          color: "rgba(45, 212, 191, 0.4)", // teal
          width: 1,
          style: 3, // dashed
          labelBackgroundColor: "#2dd4bf",
        },
        horzLine: {
          color: "rgba(45, 212, 191, 0.4)",
          width: 1,
          style: 3,
          labelBackgroundColor: "#2dd4bf",
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
      lineColor: "#2dd4bf", // teal-400
      topColor: "rgba(45, 212, 191, 0.4)",
      bottomColor: "rgba(45, 212, 191, 0.0)",
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
  }, [height]);

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
