"use client";

import React, { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, AlertCircle } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { fundApiClient, StrategyView } from "@/lib/fund_api";

interface Props {
  strategy: StrategyView | null;
  onClose: () => void;
  onSuccess: () => void;
}

export function AllocationModal({ strategy, onClose, onSuccess }: Props) {
  const [pct, setPct] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    if (strategy) setPct(strategy.allocation_pct ?? 0);
  }, [strategy]);

  if (!strategy) return null;

  const submit = async () => {
    if (pct < 0 || pct > 100) {
      setError("Allocation must be between 0 and 100%.");
      return;
    }
    try {
      setLoading(true);
      setError(null);
      await fundApiClient.setAllocation(strategy.strategy_id, pct);
      toast({ title: "Allocation set", description: `${strategy.name} target ${pct}%.` });
      onSuccess();
      onClose();
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || "Failed to set allocation.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={!!strategy} onOpenChange={onClose}>
      <DialogContent className="bg-[var(--kt-surface)] border-[var(--kt-border)] text-[var(--kt-text-strong)] w-[calc(100%-2rem)] max-w-[380px]">
        <DialogHeader>
          <DialogTitle>Allocate — {strategy.name}</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="pct">Target allocation (% of NAV)</Label>
            <Input
              id="pct"
              type="number"
              value={pct}
              onChange={(e) => setPct(parseFloat(e.target.value) || 0)}
              className="bg-[var(--kt-inset)] border-[var(--kt-border)]"
            />
          </div>
          {error && (
            <div className="text-[var(--kt-down)] text-sm flex items-center gap-2">
              <AlertCircle size={16} /> {error}
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} className="bg-transparent border-[var(--kt-border)] text-[var(--kt-text-dim)]">
            Cancel
          </Button>
          <Button
            onClick={submit}
            disabled={loading}
            className="bg-gradient-to-r from-blue-600 to-purple-600 text-[var(--kt-text-strong)]"
          >
            {loading && <Loader2 className="animate-spin mr-2" size={16} />}
            {loading ? "Saving..." : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
