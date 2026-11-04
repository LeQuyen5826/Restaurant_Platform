// Pipeline CI: Checkout -> Build -> Unit test -> Integration test -> Báo cáo
// Chạy trên Jenkins cài ở máy Windows có Git, Python 3.12+, Node 20+, Docker Desktop.
pipeline {
  agent any
  options {
    timestamps()
    timeout(time: 20, unit: 'MINUTES')
    disableConcurrentBuilds()   // chỉ một build dùng cổng 5434 tại một thời điểm
  }
  environment {
    DATABASE_URL = 'postgresql+psycopg://rb:rb@127.0.0.1:5434/rb_ci'
    JWT_SECRET   = 'ci-only-secret'
    CI_COMPOSE   = 'docker compose -p rbci -f docker-compose.ci.yml'
  }
  stages {
    stage('1. Checkout') {
      steps { checkout scm }
    }
    stage('2. Build') {
      steps {
        dir('backend') {
          bat 'python -m venv .venv'
          bat '.venv\\Scripts\\python -m pip install -q -r requirements.txt'
        }
        dir('frontend') {
          bat 'npm ci'
          bat 'npm run build'
        }
      }
    }
    stage('3. Unit test') {
      steps {
        dir('backend') { bat '.venv\\Scripts\\python -m pytest -m unit --junitxml=unit.xml' }
      }
      post { always { junit allowEmptyResults: true, testResults: 'backend/unit.xml' } }
    }
    stage('4. Integration test') {
      steps {
        // Don container cu con sot lai tu build truoc
        bat "%CI_COMPOSE% down -v"
        bat "%CI_COMPOSE% up -d --wait db"
        // Cho cong 5434 tren host thuc su mo (healthy chi nghia la Postgres chay trong container)
        bat 'powershell -NoProfile -Command "$ok=$false; for($i=0;$i -lt 30;$i++){ if((Test-NetConnection 127.0.0.1 -Port 5434 -WarningAction SilentlyContinue).TcpTestSucceeded){$ok=$true;break}; Start-Sleep -Seconds 2 }; if(-not $ok){ exit 1 }; Start-Sleep -Seconds 3"'
        dir('backend') {
          retry(3) {
            bat 'ping -n 4 127.0.0.1 >nul & .venv\\Scripts\\alembic upgrade head'
          }
          bat '.venv\\Scripts\\python -m pytest -m integration --junitxml=integration.xml'
        }
      }
      post {
        always {
          junit allowEmptyResults: true, testResults: 'backend/integration.xml'
          bat "%CI_COMPOSE% down -v"
        }
      }
    }
    stage('5. Báo cáo') {
      steps { archiveArtifacts artifacts: 'backend/*.xml, frontend/dist/**', allowEmptyArchive: true }
    }
  }
  post {
    success { echo 'SUCCESS: code hợp lệ, có thể merge'; script { notifyTeam('✅ SUCCESS') } }
    failure { echo 'FAILURE: xem log và báo cáo test để sửa'; script { notifyTeam('❌ FAILURE') } }
  }
}

// Gửi tin vào kênh Discord của nhóm. Cần Credential kiểu "Secret text" có ID = discord-webhook.
// Chưa tạo credential thì bỏ qua, build không bị lỗi.
def notifyTeam(String status) {
  try {
    withCredentials([string(credentialsId: 'discord-webhook', variable: 'HOOK')]) {
      def msg = "${status} ${env.JOB_NAME} #${env.BUILD_NUMBER} - ${env.BUILD_URL}"
      withEnv(["MSG=${msg}"]) {
        bat 'powershell -NoProfile -Command "Invoke-RestMethod -Method Post -Uri $env:HOOK -ContentType application/json -Body (@{content=$env:MSG} | ConvertTo-Json)"'
      }
    }
  } catch (e) {
    echo "Bỏ qua thông báo: ${e.message}"
  }
}