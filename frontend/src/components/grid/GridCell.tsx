"use client";

/**
 * GridCell — thin re-export wrapper around EditableCell.
 *
 * Provides a stable public API for the grid cell so the rest of the app
 * can import from "@/components/grid/GridCell" without knowing the internal
 * implementation details.
 */
export { default } from "./EditableCell";
