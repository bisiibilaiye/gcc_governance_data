# GCC Stock Exchange Data Extraction Pipeline

## 🎯 **Pure Web Extraction Process**
**Automated Corporate Data Harvesting from Public Sources**

---

## 🔍 **Extraction Targets**

### **Company Information**
- Company Name, Symbol, ISIN
- Sector Classification, Market Segment  
- Listing Date, Trading Name
- Incorporation Date, Share Capital
- Company Type, Commercial ID, Activity

### **Board Governance Data**
- Board Member Names & Positions
- Role Categories (Executive, Non-Executive, Independent)
- Member Types, Designations
- Comments and Additional Details

---

## ⚙️ **Technical Extraction Architecture**

```
Exchange Website → Browser Pool → Data Extraction → Structured Output
       ↓              ↓               ↓               ↓
   Public Pages   Selenium Grid   XPath Selectors   CSV/Excel
```

### **Multi-Browser Concurrent Processing**
- **Browser Pool**: 2-4 concurrent Selenium instances per exchange
- **Async Processing**: Non-blocking I/O for maximum throughput
- **Resource Management**: Automatic browser lifecycle management
- **Memory Efficiency**: Streaming extraction without data accumulation

---

## 🛠️ **Extraction Methodology**

### **Step 1: URL Discovery**
```python
# Exchange-specific company listing pages
get_company_urls() → List[company_page_urls]
```

### **Step 2: Concurrent Data Extraction**
```python
# Parallel processing with rate limiting
async process_single_company():
    company = extract_company_info()
    details = extract_company_details() 
    board_members = extract_board_members()
    return structured_data
```

### **Step 3: Real-Time Streaming**
```python
# Immediate data persistence
stream_company_data() → CSV files → Excel conversion
```

---

## 🎪 **Selector Strategy**

### **Robust Element Targeting**
- **Primary Selectors**: XPath expressions for reliable element location
- **Fallback Selectors**: Multiple selector strategies per data point
- **Dynamic Content**: Infinite scroll and pagination handling
- **Language Support**: Arabic/English text extraction

### **Exchange-Specific Configurations**
```yaml
selectors:
  company_name: ["h1.company-title", ".company-name"]
  board_section: ["#board-info", ".governance-section"]
  member_cards: [".member-item", "tr.board-member"]
```

---

## 📊 **Extraction Performance**

| Metric | Value | Details |
|--------|-------|---------|
| **Concurrent Browsers** | 2-4 per exchange | Optimized per site capacity |
| **Processing Speed** | 4.4s avg/company | Including all data points |
| **Success Rate** | 95-100% | With retry mechanisms |
| **Data Throughput** | 600+ companies | Full extraction run |
| **Board Members** | 5,000+ extracted | Per complete cycle |

---

## 🔄 **Error Handling & Resilience**

### **Retry Logic**
- **Exponential Backoff**: 2-10 second delays between retries
- **Maximum Attempts**: 3 retries per failed extraction
- **Exception Handling**: Graceful failure with partial data retention

### **Rate Limiting**
- **Configurable Delays**: 0.8-2.0s between requests per exchange
- **Server Respect**: Prevents overwhelming target websites
- **Adaptive Throttling**: Slower exchanges get longer delays

---

## 📤 **Structured Output Format**

### **Real-Time Data Streaming**
```
Raw HTML → Parsed Data → CSV Stream → Excel Workbook
    ↓           ↓           ↓            ↓
Selenium    Python     Immediate     Multi-sheet
Browser     Objects    Persistence   Format
```

### **Output Structure**
- **Companies Sheet**: Basic company information (8 columns)
- **Company Details Sheet**: Extended company data (13 columns)  
- **Board Members Sheet**: Individual member records (9 columns)

---

## 🚀 **Extraction Efficiency**

### **Concurrent Processing Benefits**
- **2-3x Speed Improvement** over sequential extraction
- **Resource Optimization** through browser pool management
- **Memory Efficiency** via streaming architecture
- **Fault Tolerance** with independent browser instances

### **Exchange-Specific Optimizations**
- **DFM**: 4 browsers, 0.8s delay (fast, stable)
- **Saudi**: 3 browsers, 1.2s delay (complex pagination)
- **Kuwait**: 4 browsers, 0.8s delay (reliable performance)
- **ADX**: 3 browsers, 1.0s delay (infinite scroll handling)
- **Bahrain**: 3 browsers, 1.5s delay (smaller exchange)
- **Oman**: 2 browsers, 2.0s delay (slower responses)