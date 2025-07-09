// 포트폴리오 API 클라이언트

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api'

export interface Portfolio {
  id: number
  name: string
  description?: string
  holdings_count: number
  total_investment: number
  current_value: number
  total_profit_loss: number
  total_profit_loss_percent: number
  holdings: PortfolioHolding[]
  created_at: string
  updated_at: string
}

export interface PortfolioHolding {
  id: number
  stock_code: string
  stock_name: string
  sector?: string
  market?: string
  quantity: number
  average_price: number
  current_price: number
  weight: number
  total_investment: number
  current_value: number
  profit_loss: number
  profit_loss_percent: number
  created_at: string
  updated_at: string
}

export interface CreatePortfolioRequest {
  name: string
  description?: string
}

export interface CreateHoldingRequest {
  stock_code: string
  quantity: number
  average_price: number
}

class PortfolioAPI {
  private baseUrl: string

  constructor() {
    this.baseUrl = `${API_BASE_URL}/portfolios`
  }

  // 포트폴리오 목록 조회
  async getPortfolios(): Promise<Portfolio[]> {
    try {
      const response = await fetch(`${this.baseUrl}/`)
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      return await response.json()
    } catch (error) {
      console.error('포트폴리오 목록 조회 실패:', error)
      throw error
    }
  }

  // 포트폴리오 상세 조회
  async getPortfolio(portfolioId: number): Promise<Portfolio> {
    try {
      const response = await fetch(`${this.baseUrl}/${portfolioId}/`)
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      return await response.json()
    } catch (error) {
      console.error('포트폴리오 상세 조회 실패:', error)
      throw error
    }
  }

  // 포트폴리오 생성
  async createPortfolio(data: CreatePortfolioRequest): Promise<Portfolio> {
    try {
      const response = await fetch(`${this.baseUrl}/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      })
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      return await response.json()
    } catch (error) {
      console.error('포트폴리오 생성 실패:', error)
      throw error
    }
  }

  // 포트폴리오 수정
  async updatePortfolio(portfolioId: number, data: Partial<CreatePortfolioRequest>): Promise<Portfolio> {
    try {
      const response = await fetch(`${this.baseUrl}/${portfolioId}/`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      })
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      return await response.json()
    } catch (error) {
      console.error('포트폴리오 수정 실패:', error)
      throw error
    }
  }

  // 포트폴리오 삭제
  async deletePortfolio(portfolioId: number): Promise<void> {
    try {
      const response = await fetch(`${this.baseUrl}/${portfolioId}/`, {
        method: 'DELETE',
      })
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
    } catch (error) {
      console.error('포트폴리오 삭제 실패:', error)
      throw error
    }
  }

  // 보유종목 목록 조회
  async getHoldings(portfolioId: number): Promise<PortfolioHolding[]> {
    try {
      const response = await fetch(`${this.baseUrl}/${portfolioId}/holdings/`)
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      return await response.json()
    } catch (error) {
      console.error('보유종목 목록 조회 실패:', error)
      throw error
    }
  }

  // 보유종목 추가
  async addHolding(portfolioId: number, data: CreateHoldingRequest): Promise<PortfolioHolding> {
    try {
      const response = await fetch(`${this.baseUrl}/${portfolioId}/holdings/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      })
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.message || `HTTP error! status: ${response.status}`)
      }
      return await response.json()
    } catch (error) {
      console.error('보유종목 추가 실패:', error)
      throw error
    }
  }

  // 보유종목 수정
  async updateHolding(
    portfolioId: number, 
    holdingId: number, 
    data: Partial<CreateHoldingRequest>
  ): Promise<PortfolioHolding> {
    try {
      const response = await fetch(`${this.baseUrl}/${portfolioId}/holdings/${holdingId}/`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      })
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      return await response.json()
    } catch (error) {
      console.error('보유종목 수정 실패:', error)
      throw error
    }
  }

  // 보유종목 삭제
  async deleteHolding(portfolioId: number, holdingId: number): Promise<void> {
    try {
      const response = await fetch(`${this.baseUrl}/${portfolioId}/holdings/${holdingId}/`, {
        method: 'DELETE',
      })
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
    } catch (error) {
      console.error('보유종목 삭제 실패:', error)
      throw error
    }
  }

  // 포트폴리오 비중 재계산
  async updateWeights(portfolioId: number): Promise<Portfolio> {
    try {
      const response = await fetch(`${this.baseUrl}/${portfolioId}/update-weights/`, {
        method: 'POST',
      })
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      const result = await response.json()
      return result.portfolio
    } catch (error) {
      console.error('포트폴리오 비중 재계산 실패:', error)
      throw error
    }
  }
}

export const portfolioApi = new PortfolioAPI() 