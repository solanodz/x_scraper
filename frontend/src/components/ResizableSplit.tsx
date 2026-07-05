"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

const HANDLE_SIZE = 4;

interface ResizableSplitProps {
  orientation?: "horizontal" | "vertical";
  first: ReactNode;
  second: ReactNode;
  minFirst: number;
  minSecond: number;
  defaultSecond: number;
}

export default function ResizableSplit({
  orientation = "horizontal",
  first,
  second,
  minFirst,
  minSecond,
  defaultSecond,
}: ResizableSplitProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [secondSize, setSecondSize] = useState(defaultSecond);
  const dragging = useRef(false);
  const isHorizontal = orientation === "horizontal";

  const clampSecondSize = useCallback(
    (next: number, containerSize: number) => {
      const maxSecond = containerSize - minFirst - HANDLE_SIZE;
      return Math.min(Math.max(next, minSecond), Math.max(minSecond, maxSecond));
    },
    [minFirst, minSecond],
  );

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const syncSize = () => {
      const rect = container.getBoundingClientRect();
      const containerSize = isHorizontal ? rect.width : rect.height;
      setSecondSize((current) => clampSecondSize(current, containerSize));
    };

    syncSize();
    const observer = new ResizeObserver(syncSize);
    observer.observe(container);
    return () => observer.disconnect();
  }, [clampSecondSize, isHorizontal]);

  useEffect(() => {
    function onMouseMove(e: MouseEvent) {
      if (!dragging.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const next = isHorizontal
        ? rect.right - e.clientX
        : rect.bottom - e.clientY;
      const containerSize = isHorizontal ? rect.width : rect.height;
      setSecondSize(clampSecondSize(next, containerSize));
    }

    function onMouseUp() {
      dragging.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    }

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
  }, [clampSecondSize, isHorizontal]);

  function startDrag() {
    dragging.current = true;
    document.body.style.cursor = isHorizontal ? "col-resize" : "row-resize";
    document.body.style.userSelect = "none";
  }

  const handleClass = isHorizontal
    ? "cursor-col-resize border-x border-zinc-800"
    : "cursor-row-resize border-y border-zinc-800";

  return (
    <div
      ref={containerRef}
      className={
        isHorizontal
          ? "flex min-h-0 flex-1"
          : "flex h-full min-h-0 flex-col"
      }
    >
      <div className="min-h-0 min-w-0 flex-1 overflow-hidden">{first}</div>

      <button
        type="button"
        aria-label="Resize panels"
        onMouseDown={startDrag}
        className={`shrink-0 bg-zinc-900 transition-colors hover:bg-amber-600/25 active:bg-amber-600/40 ${handleClass}`}
        style={
          isHorizontal
            ? { width: HANDLE_SIZE }
            : { height: HANDLE_SIZE }
        }
      />

      <div
        className="min-h-0 shrink-0 overflow-hidden"
        style={
          isHorizontal
            ? { width: secondSize }
            : { height: secondSize }
        }
      >
        {second}
      </div>
    </div>
  );
}
