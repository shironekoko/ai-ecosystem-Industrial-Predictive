# Labeling Feature Module

โมดูลนี้ใช้สำหรับการจัดการงานด้าน Data Labeling โดยเชื่อมต่อและทำงานร่วมกับ **Label Studio** (ผ่าน `label-studio-sdk`)

## ภาพรวมสถาปัตยกรรม

- **Router (`router.py`)**: กำหนด API Endpoints ทั้งหมดที่มี `prefix="/labeling"`
- **Service (`service.py`)**: จัดการ Business logic และสื่อสารกับ Label Studio โดยตรง ผ่าน SDK client (ใช้งานจาก `core.label_studio_client`)
- **Schemas (`schemas.py`)**: กำหนด Pydantic Models ทั้งหมดสำหรับการรับส่งข้อมูล Request/Response เพื่อตรวจสอบความถูกต้อง

## API Endpoints ทั้งหมด

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/labeling/projects` | ดึงรายการโปรเจกต์ทั้งหมดที่มีอยู่ใน Label Studio |
| `POST` | `/labeling/projects` | สร้างโปรเจกต์ใหม่ โดยส่งข้อมูล `title`, `description` และ `label_config` |
| `GET` | `/labeling/projects/{project_id}` | ดึงข้อมูลรายละเอียดของโปรเจกต์ตาม ID ที่ระบุ |
| `DELETE` | `/labeling/projects/{project_id}` | ลบโปรเจกต์และข้อมูลที่เกี่ยวข้อง |
| `GET` | `/labeling/projects/{project_id}/tasks` | ดึงรายการ tasks ที่รอการ label ในโปรเจกต์ |
| `POST` | `/labeling/projects/{project_id}/tasks` | นำเข้า tasks (Import) ทีละหลายรายการเข้าโปรเจกต์ |
| `POST` | `/labeling/setup` | สร้างโปรเจกต์ตัวอย่าง 3 แบบ อัตโนมัติ |

## ตัวอย่าง Label Configurations (XML)

Label Studio ใช้ XML ในการออกแบบหน้าตา UI สำหรับการติดฉลากข้อมูล ตัวอย่างเช่น:

### 1. Sentiment Analysis
```xml
<View>
  <Header value="Classify the sentiment of the text:"/>
  <Text name="text" value="$text"/>
  <Choices name="sentiment" toName="text" choice="single" showInLine="true">
    <Choice value="Positive"/>
    <Choice value="Negative"/>
    <Choice value="Neutral"/>
  </Choices>
</View>
```

### 2. Named Entity Recognition (NER)
```xml
<View>
  <Labels name="label" toName="text">
    <Label value="Person" background="red"/>
    <Label value="Organization" background="blue"/>
    <Label value="Location" background="green"/>
  </Labels>
  <Text name="text" value="$text"/>
</View>
```

### 3. Image Classification
```xml
<View>
  <Image name="image" value="$image"/>
  <Choices name="choice" toName="image" choice="single">
    <Choice value="Cat"/>
    <Choice value="Dog"/>
    <Choice value="Other"/>
  </Choices>
</View>
```
