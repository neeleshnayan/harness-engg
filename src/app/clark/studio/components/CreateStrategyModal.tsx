"use client";

import React, { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, AlertCircle } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { fundApiClient } from "@/lib/fund_api";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function CreateStrategyModal({ isOpen, onClose, onSuccess }: Props) {
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();

  const submit = async () => {
    if (!name.trim()) {
      setError("Strategy name is required.");
      return;
    }
    try {
      setLoading(true);
      setError(null);
      await fundApiClient.registerStrategy(name.trim());
      toast({ title: "Strategy created", description: `'${name.trim()}' registered as a draft.` });
      setName("");
      onSuccess();
      onClose();
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || "Failed to create strategy.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="bg-zinc-900 border-zinc-800 text-white w-[calc(100%-2rem)] max-w-[425px]">
        <DialogHeader>
          <DialogTitle>New Strategy</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="sname">Strategy Name</Label>
            <Input
              id="sname"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Momentum"
              className="bg-zinc-800 border-zinc-700"
            />
          </div>
          {error && (
            <div className="text-red-400 text-sm flex items-center gap-2">
              <AlertCircle size={16} /> {error}
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} className="bg-transparent border-zinc-700 text-zinc-300">
            Cancel
          </Button>
          <Button
            onClick={submit}
            disabled={loading}
            className="bg-gradient-to-r from-blue-600 to-purple-600 text-white"
          >
            {loading && <Loader2 className="animate-spin mr-2" size={16} />}
            {loading ? "Creating..." : "Create"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
