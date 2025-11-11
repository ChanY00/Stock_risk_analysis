import type { Metadata } from "next"
import { Inter, Edu_NSW_ACT_Foundation, Playfair_Display, Poppins } from "next/font/google"
import { AuthProvider } from "@/contexts/AuthContext"
import { ThemeProvider } from "@/components/theme-provider"
import "./globals.css"

const inter = Inter({ 
  subsets: ["latin"],
  weight: ['300', '400', '500', '600', '700', '800'],
  display: 'swap',
  variable: '--font-inter'
})
const poppins = Poppins({ 
  subsets: ["latin"],
  weight: ['300', '400', '500', '600', '700', '800'],
  display: 'swap',
  variable: '--font-poppins'
})
const eduFont = Edu_NSW_ACT_Foundation({ 
  subsets: ["latin"],
  variable: '--font-edu-nsw-act'
})
const playfair = Playfair_Display({
  subsets: ["latin"],
  weight: ['400', '600', '700'],
  variable: '--font-playfair'
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
      <body className={`${inter.className} ${eduFont.variable} ${playfair.variable} ${poppins.variable} antialiased`}>
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
