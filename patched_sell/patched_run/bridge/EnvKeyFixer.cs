using System;
using System.Reflection;
using System.Security;

[assembly: AllowPartiallyTrustedCallers]

namespace EnvKeyFixer
{
    [SecurityCritical]
    public class FixerDomainManager : AppDomainManager
    {
        [SecurityCritical]
        public override void InitializeNewDomain(AppDomainSetup appDomainInfo)
        {
            base.InitializeNewDomain(appDomainInfo);
            AppDomain.CurrentDomain.AssemblyLoad += OnAssemblyLoad;
        }

        [SecurityCritical]
        private static void OnAssemblyLoad(object sender, AssemblyLoadEventArgs args)
        {
            Assembly asm = args.LoadedAssembly;
            if (asm.GetName().Name == "rapiplus")
            {
                try
                {
                    Type constType = asm.GetType("com.omnesys.rapi.Constants");
                    if (constType != null)
                    {
                        FieldInfo field = constType.GetField("DEFAULT_ENVIRONMENT_KEY",
                            BindingFlags.Public | BindingFlags.Static);
                        if (field != null)
                        {
                            string oldVal = field.GetValue(null) as string;
                            field.SetValue(null, "Rithmic Paper Trading Chicago");
                            Console.Error.WriteLine("[EnvKeyFixer] Patched DEFAULT_ENVIRONMENT_KEY: '" +
                                oldVal + "' -> 'RithmicPaperTradingChicago'");
                        }
                    }
                }
                catch (Exception ex)
                {
                    Console.Error.WriteLine("[EnvKeyFixer] Error: " + ex.Message);
                }
            }
        }
    }
}
