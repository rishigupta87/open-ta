# 🐛 Admin Dashboard Debugging Guide

## ✅ **Debugging Features Added**

### **1. Debug Mode Toggle**
- **Location**: Sidebar checkbox "🐛 Debug Mode"
- **Purpose**: Enables comprehensive debugging information
- **Features**: Function tracing, variable inspection, interactive breakpoints

### **2. Debug Utilities**

#### **Function Debugging**
```python
debug_function("function_name", *args, **kwargs)
```
- Logs function calls with parameters
- Shows execution flow in UI
- Helps track function execution order

#### **Variable Inspection**
```python
debug_variable("variable_name", value)
```
- Displays variable values in UI
- JSON formatting for complex data
- Real-time variable monitoring

#### **Interactive Breakpoints**
```python
debug_breakpoint("breakpoint_label", data=None)
```
- Pauses execution for inspection
- Interactive debugging controls
- Data examination capabilities

### **3. Enhanced GraphQL Debugging**

#### **Query Inspection**
- Shows GraphQL queries being executed
- Displays query variables
- Response status monitoring
- Error analysis with stack traces

#### **Response Analysis**
- JSON response formatting
- Error detail expansion
- Network timing information
- Header inspection

### **4. Sidebar Debug Dashboard**

#### **Real-time Monitoring**
- **Debug Level Control**: INFO/DEBUG/WARNING/ERROR
- **Function Tracing**: Toggle call tracking
- **Performance Check**: API response timing
- **Memory Usage**: Process memory monitoring

#### **Testing Tools**
- **GraphQL Connection Test**: Verify backend connectivity
- **Session State Dump**: Inspect Streamlit session
- **Cache Management**: Clear debug cache

## 🎯 **How to Use Debugging**

### **Step 1: Enable Debug Mode**
1. Open admin dashboard: http://localhost:8501 → "Admin Dashboard"
2. Check **"🐛 Debug Mode"** in sidebar
3. Debug panels will appear throughout the interface

### **Step 2: Interactive Debugging**

#### **Function Call Tracing**
```
🔍 Debug: Calling get_market_status
Args: ()
Kwargs: {}
```

#### **Variable Inspection**
```
🔍 Debug Variable: market_status_result
{
  "data": {
    "getMarketStatus": {
      "success": true,
      "currentDay": "Saturday"
    }
  }
}
```

#### **Breakpoint Controls**
```
🔍 Debug Breakpoint: Market Status Section Start
[📊 Inspect Data] [📝 View Logs] [▶️ Continue]
```

### **Step 3: Performance Analysis**

#### **API Response Time**
- Click **"⏱️ Performance Check"** in sidebar
- Shows API response timing
- Helps identify slow operations

#### **Memory Usage**
- Real-time memory consumption
- Process resource monitoring
- Memory leak detection

### **Step 4: Error Debugging**

#### **GraphQL Errors**
```
🔍 Debug: GraphQL Errors
Error 1: {
  "message": "Field not found",
  "locations": [{"line": 5, "column": 3}]
}
```

#### **Network Errors**
```
🔍 Debug: Network Error Details
Traceback (most recent call last):
  File "admin.py", line 45, in execute_graphql_query
  ...
```

## 🛠️ **Debug Controls Reference**

### **Sidebar Debug Dashboard**
- **Debug Level**: Adjust logging verbosity
- **Trace Functions**: Enable/disable function call tracking
- **Performance Check**: Measure API response times
- **Memory Usage**: Monitor resource consumption

### **GraphQL Query Debugging**
- **Query Details**: Expand to see full GraphQL query
- **Response Details**: Expand to see full API response
- **Set Breakpoint**: Interactive debugging pause points

### **Interactive Breakpoints**
- **📊 Inspect Data**: View data structures
- **📝 View Logs**: Instructions for container logs
- **▶️ Continue**: Resume execution

## 🔍 **Debugging Scenarios**

### **Scenario 1: API Not Responding**
1. Enable Debug Mode
2. Check "🔌 System Status" section
3. Click "🔍 Test GraphQL Connection"
4. View network error details
5. Check container logs: `docker-compose logs backend`

### **Scenario 2: Market Status Issues**
1. Enable Debug Mode
2. Observe "Market Status Section Start" breakpoint
3. Inspect `market_status_response` variable
4. Check GraphQL query and response
5. Verify data transformation logic

### **Scenario 3: Signal Processing Errors**
1. Enable Debug Mode
2. Set breakpoints in signal processing functions
3. Inspect signal data structures
4. Check filtering and transformation logic
5. Monitor performance metrics

### **Scenario 4: UI Component Issues**
1. Enable Debug Mode
2. Use "📊 Dump Session State" to inspect Streamlit state
3. Check variable values before UI rendering
4. Monitor function call sequences
5. Clear cache if needed

## 📊 **Debug Output Examples**

### **Function Tracing**
```
🔍 Debug: Calling get_market_status
🔍 Debug: Calling execute_graphql_query
🔍 Debug: GraphQL Query
Query Details: [Expandable]
Response Details: [Expandable]
🔍 Debug Variable: market_status_result
```

### **Error Analysis**
```
❌ Network Error: Connection timeout
🔍 Debug: Network Error Details
requests.exceptions.ConnectTimeout: HTTPSConnectionPool...
```

### **Performance Metrics**
```
API Response Time: 0.45s
Memory Usage: 127.3 MB
Function Calls: 12
```

## 🎯 **Best Practices**

### **Development Debugging**
1. Always enable Debug Mode during development
2. Use breakpoints to inspect data flow
3. Monitor performance regularly
4. Check memory usage for leaks

### **Production Debugging**
1. Disable Debug Mode in production
2. Use logging for error tracking
3. Monitor API response times
4. Set up proper error handling

### **Troubleshooting Workflow**
1. **Identify Issue**: Enable debug mode, observe symptoms
2. **Isolate Cause**: Use breakpoints to narrow down location
3. **Inspect Data**: Check variable values and API responses
4. **Test Fix**: Verify resolution with performance checks
5. **Monitor**: Continue monitoring for recurring issues

## ✅ **Debug Features Summary**

- [x] **Interactive Debug Mode Toggle**
- [x] **Function Call Tracing**
- [x] **Variable Value Inspection**
- [x] **GraphQL Query/Response Debugging**
- [x] **Interactive Breakpoints**
- [x] **Performance Monitoring**
- [x] **Memory Usage Tracking**
- [x] **Error Stack Traces**
- [x] **Session State Inspection**
- [x] **Cache Management**

The admin dashboard now provides comprehensive debugging capabilities for efficient development and troubleshooting! 🎯🐛
