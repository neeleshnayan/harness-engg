import { useState, useCallback } from 'react'

interface Toast {
  id: string
  title?: string | React.ReactNode
  description?: string
  action?: React.ReactNode
}

export function useToast() {
  const [toasts, setToasts] = useState<Toast[]>([])

  const toast = useCallback(({ title, description, action }: Omit<Toast, 'id'>) => {
    const id = Math.random().toString(36).slice(2, 11)
    const newToast = { id, title, description, action }
    
    setToasts(prev => [...prev, newToast])
    
    // Auto remove after 5 seconds
    setTimeout(() => {
      setToasts(prev => prev.filter(toast => toast.id !== id))
    }, 5000)
  }, [])

  const dismiss = useCallback((toastId: string) => {
    setToasts(prev => prev.filter(toast => toast.id !== toastId))
  }, [])

  return {
    toast,
    dismiss,
    toasts,
  }
} 