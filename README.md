# CytoWatcher Django Ver.

## install
#### - 바나나 파이에 미리 설치되어 있는 경우 이 아래 세 줄은 생략 -
sudo pip install 'django<2.0'  
sudo pip install django-chartit  
sudo apt-get install python-scipy –y  

#### Excel download 버튼이 있는 버전의 경우 아래 두 줄을 추가로 입력
sudo pip install django-excel  
sudo pip install pyexcel-xlsx

## 접속 방법
run_cyto 실행 후
http://아이피주소:8000 접속
## 공유기에 연결된 경우
인터넷 브라우저로 공유기 환경 설정 페이지 (http://192.168.0.1) 접속 후 8000번 포트 포트포워딩 설정

## 그래프 축 고정 / 해제 방법
views.py  
def graph() 함수 chart_options의 x, yAxis수정  

#### ex:
'yAxis': {  
	'min': 0,  
	'max': 30000  
}

##
