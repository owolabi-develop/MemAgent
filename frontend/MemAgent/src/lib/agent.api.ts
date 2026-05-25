import { toast } from 'react-toastify';
interface QueryProps {
    query:string;
}


export async function chatAgent({query}: QueryProps){
    try{
    const formdata = new FormData()
    formdata.append("user_query",query)
    const response  = await fetch("http://127.0.0.1:8000/chat",{
        method:"POST",
        body:formdata,
        headers: {
          accept: "application/json",
        },
    })
    if(!response.ok){
         const errorData = await response.json();
        toast(errorData.detail)
      
         return null


    }
    const data = await response.json();
    return data
} catch (error){
    console.error(error)
}
}


export async function loadConversationHistory(){
    try{
    const response  = await fetch("http://127.0.0.1:8000/load-conversation",{
        method:"GET",
        headers: {
          accept: "application/json",
        },
    })
    if(!response.ok){
         const errorData = await response.json();
        toast(errorData.detail)
      
         return null


    }
    const data = await response.json();
    return data
} catch (error){
    console.error(error)
}
}

