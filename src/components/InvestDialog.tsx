'use client';

import type { FC } from 'react';
import { useState } from 'react';
import { z } from 'zod';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogClose,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormMessage,
} from '@/components/ui/form';
import { Loader2, Send, Shield, TrendingUp, Clock } from 'lucide-react';
import type { Strategy } from '@/lib/types';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { Separator } from '@/components/ui/separator';

interface InvestDialogProps {
  strategy: Strategy | null;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (amount: number) => void;
}

const formSchema = z.object({
  amount: z.coerce.number().positive('Amount must be positive.'),
});

const gradeStyles: Record<Strategy['riskGrade'], string> = {
  A: 'bg-green-500/20 text-green-400 border-green-500/20',
  B: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/20',
  C: 'bg-orange-500/20 text-orange-400 border-orange-500/20',
  D: 'bg-red-500/20 text-red-400 border-red-500/20',
};

const InvestDialog: FC<InvestDialogProps> = ({ strategy, isOpen, onClose, onSubmit }) => {
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm({
    resolver: zodResolver(formSchema),
    defaultValues: { amount: 1000 },
  });

  const handleSubmit = (values: z.infer<typeof formSchema>) => {
    setIsSubmitting(true);
    // Simulate network delay
    setTimeout(() => {
      onSubmit(values.amount);
      setIsSubmitting(false);
      onClose();
      form.reset();
    }, 1000);
  };

  if (!strategy) return null;

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md bg-zinc-900/80 backdrop-blur-lg border border-zinc-700 rounded-xl shadow-lg">
        <DialogHeader>
          <DialogTitle className="text-2xl text-white">Invest in {strategy.name}</DialogTitle>
          <DialogDescription className="text-zinc-400">Enter the amount you'd like to invest in this strategy.</DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-3 gap-4 py-4 text-center border-y border-zinc-800 my-4">
          <div className="space-y-1">
            <p className="text-sm text-zinc-400">Net APY</p>
            <p className="font-semibold text-white">{strategy.netApy.toFixed(1)}%</p>
          </div>
          <div className="space-y-1">
            <p className="text-sm text-zinc-400">Risk Grade</p>
            <Badge variant="outline" className={cn("text-xs mx-auto", gradeStyles[strategy.riskGrade])}>{strategy.riskGrade}</Badge>
          </div>
          <div className="space-y-1">
            <p className="text-sm text-zinc-400">Cooldown</p>
            <p className="font-semibold text-white">{strategy.cooldown}</p>
          </div>
        </div>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="amount"
              render={({ field }) => (
                <FormItem>
                  <Label htmlFor="amount" className="text-white">Investment Amount</Label>
                  <div className="relative">
                    <FormControl>
                      <Input
                        id="amount"
                        type="number"
                        step="100"
                        className="text-lg pr-16 bg-zinc-800 border-zinc-600 text-white focus:ring-blue-500 focus:border-blue-500"
                        {...field}
                        value={field.value as number}
                      />
                    </FormControl>
                    <span className="absolute inset-y-0 right-0 flex items-center pr-4 font-semibold text-zinc-400">USDC</span>
                  </div>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter className="pt-4 flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={onClose} className="text-zinc-400 hover:bg-zinc-800 hover:text-white">
                Cancel
              </Button>
              <Button type="submit" disabled={isSubmitting} className="bg-blue-600 hover:bg-blue-700 text-white">
                {isSubmitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Submitting...
                  </>
                ) : (
                  <>
                    <Send className="mr-2 h-4 w-4" />
                    Submit Investment
                  </>
                )}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
};

export default InvestDialog; 