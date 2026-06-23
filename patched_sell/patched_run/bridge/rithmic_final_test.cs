using System;
using System.Reflection;
using System.Threading;
using com.omnesys.rapi;

class RithmicFinalTest
{
    public class MyAdmCallbacks : AdmCallbacks
    {
        public void EnvironmentList(int requestId, EnvironmentListInfo listInfo, OMErrors errorInfo)
        {
            Console.WriteLine("EnvironmentList: requestId=" + requestId + " error=" + errorInfo.ErrorCode + " msg=" + errorInfo.ErrorMsg);
            if (listInfo != null)
            {
                Console.WriteLine("  Environments count: " + listInfo.Environments.Count);
                foreach (string env in listInfo.Environments)
                {
                    Console.WriteLine("  - '" + env + "'");
                }
            }
        }

        public void Environment(int requestId, EnvironmentInfo envInfo, OMErrors errorInfo) 
        {
            Console.WriteLine("Environment: requestId=" + requestId + " error=" + errorInfo.ErrorCode);
        }

        public void ServiceList(int requestId, ServiceListInfo listInfo, OMErrors errorInfo) { }
        public void LoginResponse(int requestId, OMErrors errorInfo) 
        {
            Console.WriteLine("LoginResponse: requestId=" + requestId + " error=" + errorInfo.ErrorCode + " msg='" + errorInfo.ErrorMsg + "'");
        }
        public void LogoutResponse(int requestId, OMErrors errorInfo) { }
        public void UserMessage(SessionMessageInfo msgInfo) 
        {
            Console.WriteLine("UserMessage: " + (msgInfo != null ? msgInfo.Message : "null"));
        }
    }

    public class MyRCallbacks : RCallbacks
    {
        public void ListRequest(int requestId, ListInfo listInfo, OMErrors errorInfo) 
        {
            Console.WriteLine("ListRequest: error=" + errorInfo.ErrorCode);
        }
        public void SubscribeRequest(int requestId, OMErrors errorInfo) 
        {
            Console.WriteLine("SubscribeRequest: error=" + errorInfo.ErrorCode);
        }
        public void UnsubscribeRequest(int requestId, OMErrors errorInfo) { }
        public void SnapshotRequest(int requestId, SnapshotResponseInfo snapInfo, OMErrors errorInfo) 
        {
            Console.WriteLine("SnapshotRequest: error=" + errorInfo.ErrorCode);
        }
        public void HistoryRequest(int requestId, HistoryResponseInfo histInfo, OMErrors errorInfo) { }
        public void RealTimeData(RealTimeDataInfo dataInfo) 
        {
            Console.WriteLine("RealTimeData received");
        }
        public void HistoryData(HistoryDataInfo histDataInfo) { }
        public void SnapshotData(SnapshotDataInfo snapDataInfo) { }
    }

    static void Main()
    {
        Console.WriteLine("=== Rithmic Final Test ===");
        Console.WriteLine("AppDomain: " + AppDomain.CurrentDomain.FriendlyName);

        try
        {
            Console.WriteLine("Creating REngineParams...");
            var admCallbacks = new MyAdmCallbacks();
            var rCallbacks = new MyRCallbacks();
            
            var rp = new REngineParams
            {
                DmnSrvrAddr = "rituz00100.rithmic.com:443",
                LicSrvrAddr = "rituz00100.rithmic.com:443",
                AppName = "VolumetricaBridge",
                DomainName = "RithmicPaperTradingChicago",
                AdmCallbacks = admCallbacks
            };

            Console.WriteLine("Creating REngine...");
            REngine engine = new REngine(rp);
            Console.WriteLine("REngine created!");

            Console.WriteLine("Calling listEnvironments...");
            engine.listEnvironments(1);
            Console.WriteLine("listEnvironments done");

            Thread.Sleep(2000);

            Console.WriteLine("Calling login with RithmicPaperTradingChicago...");
            engine.login(rCallbacks,
                "RithmicPaperTradingChicago", "zsfxr34497@minitts.net", "12345678@@A", "rituz00100.rithmic.com:443",
                "RithmicPaperTradingChicago", "zsfxr34497@minitts.net", "12345678@@A", "rituz00100.rithmic.com:443",
                "rituz00100.rithmic.com:443",
                "", "", "", ""
            );
            Console.WriteLine("login() returned (async)");

            Thread.Sleep(5000);
        }
        catch (Exception ex)
        {
            Console.WriteLine("ERROR: " + ex.GetType().Name + ": " + ex.Message);
            if (ex.InnerException != null)
                Console.WriteLine("  Inner: " + ex.InnerException.Message);
        }

        Console.WriteLine("Done. Press Enter to exit.");
        Console.ReadLine();
    }
}
