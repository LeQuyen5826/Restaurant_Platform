// Pipeline CI/CD: Checkout -> Build -> Unit test -> Integration test -> SonarQube -> Quality Gate -> Báo cáo -> Deploy (chỉ nhánh main)
// Chạy trên Jenkins cài ở máy Windows có Git, Python 3.12+, Node 20+, Docker Desktop.
// SonarQube chạy bằng Docker ở http://localhost:9001 (xem sonarqube/docker-compose.sonarqube.yml), cần bật trước khi build nhánh main.
pipeline {
  agent any
  options {
    timestamps()
    timeout(time: 30, unit: 'MINUTES')
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
        // Dọn container cũ còn sót lại từ build trước
        bat "%CI_COMPOSE% down -v"
        bat "%CI_COMPOSE% up -d --wait db"
        // Chờ cổng 5434 trên host thực sự mở (healthy chỉ nghĩa là Postgres chạy trong container)
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
    stage('5. SonarQube') {
      // Chỉ nhánh main: bản Community không phân tích riêng từng PR/nhánh.
      when { branch 'main' }
      steps {
        script {
          def scannerHome = tool 'sonar-scanner'
          withSonarQubeEnv('sonarqube') {
            bat "\"${scannerHome}\\bin\\sonar-scanner.bat\""
          }
        }
      }
    }
    stage('6. Quality Gate') {
      // Cần webhook SonarQube -> http://host.docker.internal:8081/sonarqube-webhook/
      // Muốn chạy thử mà không chặn deploy khi chưa đạt: đổi abortPipeline thành false.
      when { branch 'main' }
      steps {
        timeout(time: 5, unit: 'MINUTES') {
          waitForQualityGate abortPipeline: true
        }
      }
    }
    stage('7. Báo cáo') {
      steps { archiveArtifacts artifacts: 'backend/*.xml, frontend/dist/**', allowEmptyArchive: true }
    }
    stage('8. Deploy') {
      // Chỉ nhánh main (sau khi Pull Request được merge). Nhánh khác và Pull Request bỏ qua stage này.
      when { branch 'main' }
      steps {
        // Dựng bản mới bằng docker-compose.deploy.yml, kiểm tra sống, tự quay về bản cũ nếu hỏng.
        bat 'backend\\.venv\\Scripts\\python scripts\\deploy.py'
      }
    }
  }
  post {
    success { echo 'SUCCESS: code hợp lệ (nhánh main thì đã deploy tại http://localhost:8090)'; script { notifyTeam('✅ SUCCESS') } }
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