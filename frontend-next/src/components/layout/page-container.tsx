"use client"

import { motion } from "framer-motion"
import { ReactNode } from "react"

interface PageContainerProps {
  children: ReactNode
  title?: string
  description?: string
}

export function PageContainer({ children, title, description }: PageContainerProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 20 }}
      transition={{ duration: 0.3 }}
      className="container py-6"
    >
      {(title || description) && (
        <div className="mb-6">
          {title && (
            <h1 className="text-3xl font-bold tracking-tight">{title}</h1>
          )}
          {description && (
            <p className="text-muted-foreground mt-2">{description}</p>
          )}
        </div>
      )}
      {children}
    </motion.div>
  )
}
