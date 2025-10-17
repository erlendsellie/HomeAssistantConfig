
class CSVParser() 
{

    


    public function getAsArray($strCSV) {
        $strContent = readfile($strCSV);
        $aryCsv = json_decode($strContent);
        return $aryCsv;
    }
}


class Consumer()
{
    public function consume(array $aryMeasurements)
    {

        //TODO sort by timestamp
        foreach($aryMeasurements as $aryMeasurement)
        {
            $this->consumeMeasurement($aryMeasurement);
        }
    }

    private function consumeMeasurement($aryMeasurement)
    {

    
        $strQuantity = $aryMeasurement['quantity'];
        $intTime = $aryMeasurement['time'];
        $strUnit = $aryMeasurement['unit'];

        $objTime = new Date($intTime);
        $objCombined = new CombinedMeasurement();
        

    }
}


class Builder()
{
    private const CSV_PATH = '/measurements.csv';


    public function build()
    {
        $objParser = new CSVParser();
        $aryCsv = $objParser->getAsArray(self::CSV_PATH);
        

        $objConsumer = new Consumer();
        $objConsumer->consume($aryCsv)
    }
}