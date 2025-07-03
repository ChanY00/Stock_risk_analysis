"use client"

import { useState, useEffect } from 'react'
import { Filter, X, Save, Trash2, RotateCcw, ChevronDown, ChevronUp } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'

// 섹터 매핑 유틸리티
import { 
  translateSectorToKorean, 
  translateSectorToEnglish, 
  KOREAN_SECTORS,
  ENGLISH_SECTORS,
  getSectorColor 
} from '@/lib/sector-mapping'

export interface FilterCriteria {
  // 기본 필터
  search?: string
  sectors?: string[]
  
  // 재무 지표 범위
  priceRange?: [number, number]
  perRange?: [number, number]
  pbrRange?: [number, number]
  roeRange?: [number, number]
  dividendYieldRange?: [number, number]
  marketCapRange?: [number, number]
  
  // 기술적 지표
  rsiRange?: [number, number]
  volumeRange?: [number, number]
  
  // 감정 분석
  sentimentRange?: [number, number]
  sentimentType?: 'positive' | 'negative' | 'neutral' | 'all'
  
  // 정렬
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
}

interface SavedFilter {
  id: string
  name: string
  criteria: FilterCriteria
  createdAt: Date
}

interface AdvancedFiltersProps {
  onFilterChange: (criteria: FilterCriteria) => void
  availableSectors?: string[]
  className?: string
}

const SORT_OPTIONS = [
  { value: 'name', label: '종목명' },
  { value: 'price', label: '현재가' },
  { value: 'change_percent', label: '변동률' },
  { value: 'volume', label: '거래량' },
  { value: 'market_cap', label: '시가총액' },
  { value: 'per', label: 'PER' },
  { value: 'pbr', label: 'PBR' },
  { value: 'roe', label: 'ROE' },
  { value: 'sentiment', label: '감정점수' }
]

const DEFAULT_RANGES = {
  price: [0, 1000000],
  per: [0, 100],
  pbr: [0, 10],
  roe: [-50, 50],
  dividendYield: [0, 20],
  marketCap: [0, 1000],
  rsi: [0, 100],
  volume: [0, 100000],
  sentiment: [0, 100]
}

export function AdvancedFilters({ 
  onFilterChange, 
  availableSectors = [],
  className = ""
}: AdvancedFiltersProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [criteria, setCriteria] = useState<FilterCriteria>({})
  const [savedFilters, setSavedFilters] = useState<SavedFilter[]>([])
  const [filterName, setFilterName] = useState('')
  const [showSaveDialog, setShowSaveDialog] = useState(false)
  
  // 섹션 접기/펼치기 상태
  const [expandedSections, setExpandedSections] = useState({
    basic: true,
    financial: false,
    technical: false,
    sentiment: false
  })

  // 로컬 스토리지에서 저장된 필터 로드
  useEffect(() => {
    const saved = localStorage.getItem('advanced-filters')
    if (saved) {
      try {
        const filters = JSON.parse(saved)
        setSavedFilters(filters)
      } catch (error) {
        console.error('Failed to load saved filters:', error)
      }
    }
  }, [])

  // 필터 변경 사항을 부모에게 전달
  useEffect(() => {
    onFilterChange(criteria)
  }, [criteria, onFilterChange])

  const updateCriteria = (updates: Partial<FilterCriteria>) => {
    setCriteria(prev => ({ ...prev, ...updates }))
  }

  const clearAllFilters = () => {
    setCriteria({})
  }

  const saveFilter = () => {
    if (!filterName.trim()) return
    
    const newFilter: SavedFilter = {
      id: Date.now().toString(),
      name: filterName.trim(),
      criteria: { ...criteria },
      createdAt: new Date()
    }
    
    const updatedFilters = [...savedFilters, newFilter]
    setSavedFilters(updatedFilters)
    localStorage.setItem('advanced-filters', JSON.stringify(updatedFilters))
    setFilterName('')
    setShowSaveDialog(false)
  }

  const loadFilter = (filter: SavedFilter) => {
    setCriteria(filter.criteria)
  }

  const deleteFilter = (filterId: string) => {
    const updatedFilters = savedFilters.filter(f => f.id !== filterId)
    setSavedFilters(updatedFilters)
    localStorage.setItem('advanced-filters', JSON.stringify(updatedFilters))
  }

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }))
  }

  const getActiveFilterCount = () => {
    let count = 0
    if (criteria.search) count++
    if (criteria.sectors?.length) count++
    if (criteria.priceRange) count++
    if (criteria.perRange) count++
    if (criteria.pbrRange) count++
    if (criteria.roeRange) count++
    if (criteria.dividendYieldRange) count++
    if (criteria.marketCapRange) count++
    if (criteria.rsiRange) count++
    if (criteria.volumeRange) count++
    if (criteria.sentimentRange) count++
    if (criteria.sentimentType && criteria.sentimentType !== 'all') count++
    return count
  }

  return (
    <div className={className}>
      <Popover open={isOpen} onOpenChange={setIsOpen}>
        <PopoverTrigger asChild>
          <Button variant="outline" className="relative">
            <Filter className="h-4 w-4 mr-2" />
            고급 필터
            {getActiveFilterCount() > 0 && (
              <Badge variant="destructive" className="ml-2 h-5 w-5 rounded-full p-0 text-xs">
                {getActiveFilterCount()}
              </Badge>
            )}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-96 p-0" align="start">
          <Card className="border-0 shadow-none">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">고급 필터</CardTitle>
                <div className="flex gap-2">
                  <Button variant="ghost" size="sm" onClick={clearAllFilters}>
                    <RotateCcw className="h-4 w-4 mr-1" />
                    초기화
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setShowSaveDialog(!showSaveDialog)}>
                    <Save className="h-4 w-4 mr-1" />
                    저장
                  </Button>
                </div>
              </div>
              <CardDescription>
                상세한 조건으로 종목을 필터링하세요
              </CardDescription>
            </CardHeader>
            
            <CardContent className="space-y-4 max-h-96 overflow-y-auto">
              {/* 저장된 필터 */}
              {savedFilters.length > 0 && (
                <div className="space-y-2">
                  <Label className="text-sm font-medium">저장된 필터</Label>
                  <div className="flex flex-wrap gap-2">
                    {savedFilters.map((filter) => (
                      <div key={filter.id} className="flex items-center gap-1">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => loadFilter(filter)}
                          className="text-xs h-7"
                        >
                          {filter.name}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => deleteFilter(filter.id)}
                          className="h-7 w-7 p-0 text-red-500 hover:text-red-700"
                        >
                          <X className="h-3 w-3" />
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 필터 저장 입력 */}
              {showSaveDialog && (
                <div className="flex gap-2">
                  <Input
                    placeholder="필터 이름"
                    value={filterName}
                    onChange={(e) => setFilterName(e.target.value)}
                    className="flex-1"
                  />
                  <Button onClick={saveFilter} size="sm">저장</Button>
                </div>
              )}

              {/* 기본 필터 */}
              <Collapsible open={expandedSections.basic} onOpenChange={() => toggleSection('basic')}>
                <CollapsibleTrigger className="flex items-center justify-between w-full p-2 hover:bg-gray-50 rounded">
                  <Label className="font-medium">기본 필터</Label>
                  {expandedSections.basic ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </CollapsibleTrigger>
                <CollapsibleContent className="space-y-3 pt-2">
                  <div>
                    <Label className="text-sm">종목명/코드 검색</Label>
                    <Input
                      placeholder="삼성전자, 005930..."
                      value={criteria.search || ''}
                      onChange={(e) => updateCriteria({ search: e.target.value })}
                    />
                  </div>

                  <div>
                    <Label className="text-sm">섹터 선택</Label>
                    <div className="mt-2 space-y-2">
                      <div className="flex flex-wrap gap-2">
                        {KOREAN_SECTORS.map((koreanSector) => {
                          const englishSector = translateSectorToEnglish(koreanSector)
                          const isSelected = criteria.sectors?.includes(englishSector) || false
                          
                          return (
                            <Button
                              key={koreanSector}
                              variant={isSelected ? "default" : "outline"}
                              size="sm"
                              onClick={() => {
                                const currentSectors = criteria.sectors || []
                                let newSectors: string[]
                                
                                if (isSelected) {
                                  newSectors = currentSectors.filter(s => s !== englishSector)
                                } else {
                                  newSectors = [...currentSectors, englishSector]
                                }
                                
                                updateCriteria({ sectors: newSectors.length > 0 ? newSectors : undefined })
                              }}
                              className={`text-xs transition-all ${
                                isSelected 
                                  ? 'shadow-md' 
                                  : 'hover:shadow-sm'
                              }`}
                              style={{
                                backgroundColor: isSelected ? getSectorColor(koreanSector) : undefined,
                                borderColor: getSectorColor(koreanSector),
                                color: isSelected ? 'white' : getSectorColor(koreanSector)
                              }}
                            >
                              {koreanSector}
                            </Button>
                          )
                        })}
                      </div>
                      {criteria.sectors && criteria.sectors.length > 0 && (
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-gray-500">선택된 섹터:</span>
                          <div className="flex flex-wrap gap-1">
                            {criteria.sectors.map((englishSector) => (
                              <Badge 
                                key={englishSector} 
                                variant="secondary" 
                                className="text-xs"
                                style={{ backgroundColor: getSectorColor(translateSectorToKorean(englishSector)) + '20' }}
                              >
                                {translateSectorToKorean(englishSector)}
                                <X 
                                  className="h-3 w-3 ml-1 cursor-pointer" 
                                  onClick={() => {
                                    const newSectors = criteria.sectors?.filter(s => s !== englishSector)
                                    updateCriteria({ sectors: newSectors?.length ? newSectors : undefined })
                                  }}
                                />
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                  
                  <div>
                    <Label className="text-sm">정렬</Label>
                    <div className="flex gap-2 mt-1">
                      <Select value={criteria.sortBy} onValueChange={(value) => updateCriteria({ sortBy: value })}>
                        <SelectTrigger className="flex-1">
                          <SelectValue placeholder="정렬 기준" />
                        </SelectTrigger>
                        <SelectContent>
                          {SORT_OPTIONS.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <Select 
                        value={criteria.sortOrder} 
                        onValueChange={(value: 'asc' | 'desc') => updateCriteria({ sortOrder: value })}
                      >
                        <SelectTrigger className="w-20">
                          <SelectValue placeholder="순서" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="asc">오름차순</SelectItem>
                          <SelectItem value="desc">내림차순</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </CollapsibleContent>
              </Collapsible>

              {/* 재무 지표 필터 */}
              <Collapsible open={expandedSections.financial} onOpenChange={() => toggleSection('financial')}>
                <CollapsibleTrigger className="flex items-center justify-between w-full p-2 hover:bg-gray-50 rounded">
                  <Label className="font-medium">재무 지표</Label>
                  {expandedSections.financial ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </CollapsibleTrigger>
                <CollapsibleContent className="space-y-3 pt-2">
                  <div>
                    <Label className="text-sm">주가 범위 (원)</Label>
                    <div className="px-2 mt-2">
                      <Slider
                        value={criteria.priceRange || DEFAULT_RANGES.price}
                        onValueChange={(value) => updateCriteria({ priceRange: value as [number, number] })}
                        max={DEFAULT_RANGES.price[1]}
                        min={DEFAULT_RANGES.price[0]}
                        step={1000}
                        className="w-full"
                      />
                      <div className="flex justify-between text-xs text-gray-500 mt-1">
                        <span>{(criteria.priceRange?.[0] || DEFAULT_RANGES.price[0]).toLocaleString()}원</span>
                        <span>{(criteria.priceRange?.[1] || DEFAULT_RANGES.price[1]).toLocaleString()}원</span>
                      </div>
                    </div>
                  </div>

                  <div>
                    <Label className="text-sm">PER 범위</Label>
                    <div className="px-2 mt-2">
                      <Slider
                        value={criteria.perRange || DEFAULT_RANGES.per}
                        onValueChange={(value) => updateCriteria({ perRange: value as [number, number] })}
                        max={DEFAULT_RANGES.per[1]}
                        min={DEFAULT_RANGES.per[0]}
                        step={1}
                        className="w-full"
                      />
                      <div className="flex justify-between text-xs text-gray-500 mt-1">
                        <span>{criteria.perRange?.[0] || DEFAULT_RANGES.per[0]}</span>
                        <span>{criteria.perRange?.[1] || DEFAULT_RANGES.per[1]}</span>
                      </div>
                    </div>
                  </div>

                  <div>
                    <Label className="text-sm">PBR 범위</Label>
                    <div className="px-2 mt-2">
                      <Slider
                        value={criteria.pbrRange || DEFAULT_RANGES.pbr}
                        onValueChange={(value) => updateCriteria({ pbrRange: value as [number, number] })}
                        max={DEFAULT_RANGES.pbr[1]}
                        min={DEFAULT_RANGES.pbr[0]}
                        step={0.1}
                        className="w-full"
                      />
                      <div className="flex justify-between text-xs text-gray-500 mt-1">
                        <span>{criteria.pbrRange?.[0] || DEFAULT_RANGES.pbr[0]}</span>
                        <span>{criteria.pbrRange?.[1] || DEFAULT_RANGES.pbr[1]}</span>
                      </div>
                    </div>
                  </div>

                  <div>
                    <Label className="text-sm">ROE 범위 (%)</Label>
                    <div className="px-2 mt-2">
                      <Slider
                        value={criteria.roeRange || DEFAULT_RANGES.roe}
                        onValueChange={(value) => updateCriteria({ roeRange: value as [number, number] })}
                        max={DEFAULT_RANGES.roe[1]}
                        min={DEFAULT_RANGES.roe[0]}
                        step={1}
                        className="w-full"
                      />
                      <div className="flex justify-between text-xs text-gray-500 mt-1">
                        <span>{criteria.roeRange?.[0] || DEFAULT_RANGES.roe[0]}%</span>
                        <span>{criteria.roeRange?.[1] || DEFAULT_RANGES.roe[1]}%</span>
                      </div>
                    </div>
                  </div>
                </CollapsibleContent>
              </Collapsible>

              {/* 감정 분석 필터 */}
              <Collapsible open={expandedSections.sentiment} onOpenChange={() => toggleSection('sentiment')}>
                <CollapsibleTrigger className="flex items-center justify-between w-full p-2 hover:bg-gray-50 rounded">
                  <Label className="font-medium">감정 분석</Label>
                  {expandedSections.sentiment ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </CollapsibleTrigger>
                <CollapsibleContent className="space-y-3 pt-2">
                  <div>
                    <Label className="text-sm">감정 유형</Label>
                    <Select 
                      value={criteria.sentimentType || 'all'} 
                      onValueChange={(value) => updateCriteria({ sentimentType: value as any })}
                    >
                      <SelectTrigger className="mt-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">전체</SelectItem>
                        <SelectItem value="positive">긍정적</SelectItem>
                        <SelectItem value="neutral">중립적</SelectItem>
                        <SelectItem value="negative">부정적</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <Label className="text-sm">감정 점수 범위</Label>
                    <div className="px-2 mt-2">
                      <Slider
                        value={criteria.sentimentRange || DEFAULT_RANGES.sentiment}
                        onValueChange={(value) => updateCriteria({ sentimentRange: value as [number, number] })}
                        max={DEFAULT_RANGES.sentiment[1]}
                        min={DEFAULT_RANGES.sentiment[0]}
                        step={5}
                        className="w-full"
                      />
                      <div className="flex justify-between text-xs text-gray-500 mt-1">
                        <span>{criteria.sentimentRange?.[0] || DEFAULT_RANGES.sentiment[0]}</span>
                        <span>{criteria.sentimentRange?.[1] || DEFAULT_RANGES.sentiment[1]}</span>
                      </div>
                    </div>
                  </div>
                </CollapsibleContent>
              </Collapsible>
            </CardContent>
          </Card>
        </PopoverContent>
      </Popover>
    </div>
  )
} 