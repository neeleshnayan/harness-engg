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

  const form = useForm<z.infer<typeof formSchema>>({
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
      <DialogContent className="sm:max-w-md bg-zinc-900 border-zinc-700">
        <DialogHeader>
          <DialogTitle className="text-2xl text-white">Invest in {strategy.name}</DialogTitle>
          <DialogDescription className="text-zinc-400">Review the terms and enter the amount you'd like to invest.</DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
            <div className="flex justify-between items-center rounded-lg bg-zinc-800/50 p-3">
              <div className="flex flex-col items-center gap-1.5 w-1/3">
                  <Badge
                    variant="outline"
                    className={cn(
                      'px-2 py-0.5 font-bold border',
                      gradeStyles[strategy.riskGrade]
                    )}
                  >
                    <Shield className="w-3.5 h-3.5 mr-1" />
                    Risk: {strategy.riskGrade}
                  </Badge>
              </div>
              <div className="flex flex-col items-center gap-1.5 w-1/3">
                <div className="flex items-center gap-1.5 text-sm">
                  <TrendingUp className="w-4 h-4 text-green-400" />
                  <span className="font-semibold text-white">{strategy.netApy.toFixed(1)}%</span>
                </div>
                <span className="text-xs text-zinc-500">{strategy.name === 'Pendle Fixed Yield' ? 'Fixed APY' : 'Net APY'}</span>
              </div>
              <div className="flex flex-col items-center gap-1.5 w-1/3">
                 <div className="flex items-center gap-1.5 text-sm">
                  <Clock className="w-4 h-4 text-zinc-400" />
                  <span className="font-semibold text-white">{strategy.cooldown}</span>
                </div>
                <span className="text-xs text-zinc-500">Lock-in Period</span>
              </div>
            </div>
        </div>

        <Separator className="bg-zinc-700" />

        <Form {...form}>
          <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="amount"
              render={({ field }) => (
                <FormItem>
                  <Label htmlFor="amount" className="text-right text-white">
                    Investment Amount
                  </Label>
                  <div className="relative">
                    <FormControl>
                      <Input
                        id="amount"
                        type="number"
                        step="100"
                        className="col-span-3 text-lg pr-16 bg-zinc-800 border-zinc-700 text-white"
                        {...field}
                      />
                    </FormControl>
                    <span className="absolute inset-y-0 right-0 flex items-center pr-4 font-semibold text-zinc-400">USDC</span>
                  </div>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter className="pt-4">
              <DialogClose asChild>
                <Button type="button" variant="secondary" className="bg-zinc-700 text-white hover:bg-zinc-600">
                  Cancel
                </Button>
              </DialogClose>
              <Button type="submit" disabled={isSubmitting} className="bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700">
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