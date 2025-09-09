import type { Metadata } from "next"
import { Roboto, Edu_NSW_ACT_Foundation } from "next/font/google"
import { AuthProvider } from "@/contexts/AuthContext"
import { ThemeProvider } from "@/components/theme-provider"
import "./globals.css"

const roboto = Roboto({ 
  subsets: ["latin"],
  weight: ['300', '400', '500', '700'],
  display: 'swap'
})
const eduFont = Edu_NSW_ACT_Foundation({ 
  subsets: ["latin"],
  variable: '--font-edu-nsw-act'
})

export const metadata: Metadata = {
  title: "Stock Analysis Dashboard",
  description: "Modern stock analysis dashboard with technical indicators and sentiment analysis",
  generator: 'v0.dev'
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <body className={`${roboto.className} ${eduFont.variable}`}>
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <AuthProvider>
            {children}
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}
