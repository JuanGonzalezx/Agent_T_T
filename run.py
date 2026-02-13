import os
from app import create_app
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

app = create_app()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV', 'production') == 'development'
    
    print(f"\n🚀 Servidor Agente T_T iniciado en puerto {port}")
    print(f"📡 Modo Debug: {debug}\n")
    
    app.run(host='0.0.0.0', port=port, debug=debug)